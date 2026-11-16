"""Two isolated Chrome contexts and real FastAPI; --sqlite uses a disposable SQLite file."""

import importlib.util
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.bootstrap_admin import bootstrap_admin  # noqa: E402
from backend.database import make_engine, make_session_factory  # noqa: E402
from backend.models import Booking, RoomNight, User  # noqa: E402
from backend.schemas import RegisterIn  # noqa: E402
from backend.tests.conftest import migrate  # noqa: E402

spec = importlib.util.spec_from_file_location("browser_ui", ROOT / "tests/ui-browser.py")
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def stop_process(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        process.terminate()
    process.wait(timeout=20)


def main():
    sqlite = "--sqlite" in sys.argv[1:]
    url = make_url(os.environ.get("TEST_POSTGRES_URL", "sqlite://"))
    if not sqlite and (url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test")):
        raise SystemExit("TEST_POSTGRES_URL must point to a dedicated PostgreSQL database ending in _test")
    browser = shutil.which("google-chrome") or os.path.join(
        os.environ.get("PROGRAMFILES", ""), "Google/Chrome/Application/chrome.exe"
    )
    if not Path(browser).is_file():
        raise SystemExit("Chrome is required")
    parent = ROOT / "backend/.test-tmp"
    parent.mkdir(exist_ok=True)
    database_directory = None
    admin_engine = None
    schema = None
    if sqlite:
        database_directory = tempfile.TemporaryDirectory(prefix="shared-sqlite-", dir=parent)
        database_url = "sqlite:///" + (Path(database_directory.name) / "shared.db").as_posix()
    else:
        schema = "luxstay_shared_" + secrets.token_hex(12)
        admin_engine = make_engine(url.render_as_string(hide_password=False))
        with admin_engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        isolated = url.set(query={**url.query, "options": "-csearch_path=" + schema})
        database_url = isolated.render_as_string(hide_password=False)
    engine = make_engine(database_url)
    factory = make_session_factory(engine)
    processes = []
    sockets = []
    server = None
    checks = []
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    def check(condition, label):
        if not condition:
            raise AssertionError(label)
        checks.append(label)

    parent = ROOT / "backend/.test-tmp"
    parent.mkdir(exist_ok=True)
    try:
        migrate(engine)
        password = secrets.token_urlsafe(24)
        with factory() as db, db.begin():
            bootstrap_admin(
                db,
                RegisterIn(
                    email="shared-admin@example.com", display_name="Shared Test Admin", password=password
                ),
            )
        with tempfile.TemporaryDirectory(
            prefix="shared-browser-", dir=parent, ignore_cleanup_errors=True
        ) as directory:
            work = Path(directory)
            port = free_port()
            origin = f"http://127.0.0.1:{port}"
            environment = os.environ.copy()
            environment.pop("FRONTEND_MODE", None)
            environment.update(
                APP_ENV="test",
                DATABASE_URL=database_url,
                JWT_SECRET=secrets.token_urlsafe(48),
                SERVE_FRONTEND="true",
                AUTH_RATE_LIMIT="1000",
                UPLOAD_DIR=str(work / "uploads"),
                CORS_ORIGINS=origin + ",http://localhost:5500,http://127.0.0.1:5500",
            )
            with (work / "server.log").open("w", encoding="utf-8") as log:

                def start_server():
                    process = subprocess.Popen(
                        [
                            sys.executable,
                            "-m",
                            "uvicorn",
                            "backend.main:app",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            str(port),
                            "--no-access-log",
                        ],
                        cwd=ROOT,
                        env=environment,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        creationflags=flags,
                    )
                    processes.append(process)
                    for _ in range(150):
                        try:
                            if httpx.get(origin + "/api/ready", timeout=2).status_code == 200:
                                return process
                        except httpx.TransportError:
                            pass
                        if process.poll() is not None:
                            raise RuntimeError("Shared test backend exited")
                        time.sleep(0.1)
                    raise RuntimeError("Shared test backend did not become ready")

                server = start_server()

                def context(name):
                    profile = work / name
                    profile.mkdir()
                    process = subprocess.Popen(
                        [
                            browser,
                            "--headless=new",
                            "--disable-gpu",
                            "--no-first-run",
                            "--remote-debugging-port=0",
                            "--user-data-dir=" + str(profile),
                            "about:blank",
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=flags,
                    )
                    processes.append(process)
                    active = profile / "DevToolsActivePort"
                    for _ in range(150):
                        if active.exists():
                            break
                        time.sleep(0.1)
                    debug_port = active.read_text().splitlines()[0]
                    targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json"))
                    tab = ui.CDP(
                        next(row["webSocketDebuggerUrl"] for row in targets if row["type"] == "page")
                    )
                    sockets.append(tab.sock)
                    tab.call("Page.enable")
                    tab.call("Runtime.enable")
                    tab.call("Network.enable")
                    tab.call("Network.setBlockedURLs", urls=["*/mock/*"])
                    navigate(
                        tab,
                        "login.html",
                        "document.querySelector('#login-form [type=submit]')?.disabled===false",
                    )
                    return tab

                def navigate(tab, route, ready):
                    tab.call("Page.navigate", url=origin + "/" + route)
                    tab.until("document.readyState==='complete' && (" + ready + ")")

                def api(tab, expression):
                    return tab.js("import('./js/api.js').then(async api=>{" + expression + "})")

                def login(tab, email):
                    return api(
                        tab,
                        "const session=await api.login("
                        + json.dumps(email)
                        + ","
                        + json.dumps(password)
                        + ");(await import('./js/auth.js')).saveSession(session);return api.getProfile();",
                    )

                def register(tab, email, name):
                    payload = {
                        "email": email,
                        "display_name": name,
                        "password": password,
                        "phone": "0912345678",
                    }
                    return api(
                        tab,
                        "const session=await api.register("
                        + json.dumps(payload)
                        + ");(await import('./js/auth.js')).saveSession(session);return api.getProfile();",
                    )

                a, b = context("browser-a"), context("browser-b")
                check(
                    a.js(
                        "import('./js/config.js').then(c=>c.SHARED_MODE && c.ACCOUNT_API_MODE && c.API_BASE===location.origin+'/api')"
                    ),
                    "shared mode uses same-origin API without query parameters",
                )
                # Local business records remain untouched and cannot become the API source.
                pollution = json.dumps(
                    {
                        "bookings": '[{"id":"LOCAL-ONLY"}]',
                        "customerBookings": '[{"id":"LOCAL-ONLY"}]',
                        "homestays": '[{"id":"LOCAL-ONLY"}]',
                        "luxstay_mock_users_v1": "[]",
                    }
                )
                for tab in (a, b):
                    tab.js(
                        "Object.entries("
                        + pollution
                        + ").forEach(([key,value])=>localStorage.setItem(key,value))"
                    )
                customer = register(a, "huy@test.com", "Shared Customer")
                remote = login(b, "huy@test.com")
                with factory() as db:
                    check(
                        customer["id"]
                        == remote["id"]
                        == db.scalar(select(User.id).where(User.email == "huy@test.com")),
                        "browser B logs in to browser A registered database user",
                    )
                check(
                    a.js('sessionStorage.getItem("luxstay_api_access_token")!==null')
                    and b.js('sessionStorage.getItem("luxstay_api_access_token")!==null'),
                    "independent contexts use separate backend sessions",
                )
                pending = register(a, "shared-host@example.com", "Shared Host")
                application_data = {
                    "homestay_name": "Shared Stay",
                    "address": "123 Shared Street",
                    "province": "Lam Dong",
                    "room_count": 1,
                    "description": "A comfortable homestay for shared database testing.",
                    "experience": "",
                    "phone": "0912345678",
                    "accept_terms": True,
                }
                application = api(a, "return api.applyHost(" + json.dumps(application_data) + ");")
                forbidden = api(a, "try{await api.getHostHomestays();return 200}catch(e){return e.status}")
                check(
                    pending["role"] == "user" and forbidden == 403,
                    "pending customer cannot access host resources",
                )
                login(b, "shared-admin@example.com")
                applications = api(b, "return api.getAdminApplications();")
                check(
                    any(row["id"] == application["id"] for row in applications),
                    "admin context reads actual pending database application",
                )
                api(b, "return api.decideHostApplication(" + str(application["id"]) + ",'approve');")
                check(
                    api(a, "try{await api.getProfile();return 200}catch(e){return e.status}") == 401,
                    "approval revokes stale customer session",
                )
                host = login(a, "shared-host@example.com")
                check(
                    host["role"] == "host" and api(a, "return api.getHostHomestays();") == [],
                    "approved host starts with empty owned catalog",
                )
                dashboard = api(a, "return api.getHostDashboard();")
                check(
                    dashboard["bookingCount"] == 0
                    and dashboard["inventoryCount"] == 0
                    and dashboard["homestayCounts"].get("active", 0) == 0,
                    "newly approved host dashboard contains zero actual business records",
                )
                stay = api(
                    a,
                    "return api.saveHostHomestay("
                    + json.dumps(
                        {
                            "name": "Shared Database Stay",
                            "description": "Shared property created through the real frontend adapter.",
                            "address": "123 Shared Street, Da Lat",
                            "amenities": [],
                            "images": [],
                            "status": "active",
                        }
                    )
                    + ");",
                )
                room = api(
                    a,
                    "return api.saveHostRoom("
                    + json.dumps(
                        {
                            "homestayId": stay["id"],
                            "name": "Shared Room",
                            "description": "Shared test room",
                            "capacity": 2,
                            "pricePerNight": 250000,
                            "inventory": 1,
                            "images": [],
                        }
                    )
                    + ");",
                )
                login(b, "shared-host@example.com")
                check(
                    any(row["id"] == stay["id"] for row in api(b, "return api.getHostHomestays();")),
                    "same host on second context reads newly created homestay",
                )
                check(
                    api(a, "try{await api.getAdminUsers();return 200}catch(e){return e.status}") == 403,
                    "host cannot access admin API",
                )
                login(a, "huy@test.com")
                navigate(a, "index.html?mode=api", "!!document.querySelector('#hero-slides article') && !!document.querySelector('#results .card')")
                check(
                    a.js("!!document.querySelector('#results .card')"),
                    "homepage renders homestays from the real API",
                )
                navigate(b, "search.html?mode=api", "!!document.querySelector('#results .card')")
                check(True, "homestay search renders catalog from the same API")
                response = httpx.get(origin + "/api/items")
                check(response.status_code == 200 and response.json()["total"] > 0, "catalog HTTP response is JSON with actual database rows")
                print(json.dumps({"catalog_request": str(response.url), "status": response.status_code, "content_type": response.headers.get("content-type"), "total": response.json()["total"], "first_id": response.json()["items"][0]["id"]}), flush=True)
                for allowed_origin in ("http://localhost:5500", "http://127.0.0.1:5500"):
                    preflight = httpx.options(origin + "/api/me/bookings", headers={"Origin": allowed_origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type,idempotency-key"})
                    check(preflight.status_code == 200 and preflight.headers.get("access-control-allow-origin") == allowed_origin, "real HTTP CORS preflight permits " + allowed_origin)
                from datetime import timedelta

                from backend.booking_service import business_today

                start = business_today() + timedelta(days=20)
                payload = {
                    "homestayId": stay["id"],
                    "checkIn": start.isoformat(),
                    "checkOut": (start + timedelta(days=2)).isoformat(),
                    "adults": 2,
                    "children": 0,
                    "rooms": [{"roomId": room["id"], "qty": 1}],
                    "guestName": "Shared Customer",
                    "guestEmail": "huy@test.com",
                }
                key = secrets.token_urlsafe(24)
                booking = api(
                    a, "return api.createBooking(" + json.dumps(payload) + "," + json.dumps(key) + ");"
                )
                replay = api(
                    a, "return api.createBooking(" + json.dumps(payload) + "," + json.dumps(key) + ");"
                )
                check(booking["id"] == replay["id"], "stable idempotency key replays one booking")
                check(
                    any(
                        str(row["id"]) == str(booking["id"])
                        for row in api(b, "return api.getHostBookings();")
                    ),
                    "owning host sees customer booking from shared database",
                )
                # Current booking engine confirms at creation. Exercise another eligible status through host API.
                check(
                    booking["status"] == "confirmed",
                    "current backend confirms saved booking with manual payment pending",
                )
                payments = api(a, "return api.getPayment(" + str(booking["id"]) + ");")
                check(
                    payments["status"] == "pending",
                    "shared booking does not fabricate paid status",
                )
                login(b, "huy@test.com")
                navigate(b, "booking-list.html", "!!document.querySelector('#booking-list .row')")
                check(
                    b.js(
                        "document.querySelector('#booking-list').textContent.includes("
                        + json.dumps(booking["homestayName"])
                        + ")"
                    ),
                    "second customer context reloads history containing the shared booking",
                )
                check(
                    b.js(
                        "(()=>{const row=document.querySelector('#booking-list .row');return getComputedStyle(row).visibility==='visible' && row.getBoundingClientRect().height>0 && !document.querySelector('#booking-list').hidden})()"
                    ),
                    "shared history row is visible to the user",
                )
                b.js(
                    "window.historyCompleted=0;window.originalHistoryFetch=window.fetch;window.fetch=async(...args)=>{const response=await originalHistoryFetch(...args);const url=String(args[0]);if(url.includes('/me/bookings?')){await new Promise(resolve=>setTimeout(resolve,url.includes('status=cancelled')?400:20));window.historyCompleted++}return response};document.querySelector('[data-filter=cancelled]').click();document.querySelector('[data-filter=all]').click()"
                )
                b.until("window.historyCompleted===2 && !!document.querySelector('#booking-list .row')")
                check(
                    b.js(
                        "document.querySelector('[data-filter=all]').classList.contains('is-active') && !!document.querySelector('#booking-list .row') && !document.querySelector('#booking-list').hidden"
                    ),
                    "slow previous status response cannot hide current booking history",
                )
                b.js("window.fetch=window.originalHistoryFetch;delete window.originalHistoryFetch")
                check(
                    api(a, "try{await api.getAdminUsers();return 200}catch(e){return e.status}") == 403,
                    "customer cannot access admin API",
                )
                with factory() as db:
                    check(
                        len(db.scalars(select(Booking)).all()) == 1
                        and len(db.scalars(select(RoomNight)).all()) == 2,
                        "Database contains one booking and exactly two reserved nights",
                    )
                register(b, "unrelated-customer@example.com", "Unrelated Customer")
                check(
                    api(b, "return api.getBookings();") == [],
                    "unrelated customer history excludes another customer booking",
                )
                for operation in ("getBooking", "cancelBooking"):
                    check(
                        api(
                            b,
                            "try{await api."
                            + operation
                            + "("
                            + str(booking["id"])
                            + ");return 200}catch(e){return e.status}",
                        )
                        == 404,
                        "unrelated customer cannot " + operation + " another customer booking",
                    )
                # A different approved host must not obtain the first host property.
                today_payload = {
                    **payload,
                    "checkIn": business_today().isoformat(),
                    "checkOut": (business_today() + timedelta(days=1)).isoformat(),
                }
                today_booking = api(
                    a,
                    "return api.createBooking("
                    + json.dumps(today_payload)
                    + ","
                    + json.dumps(secrets.token_urlsafe(24))
                    + ");",
                )
                login(b, "shared-host@example.com")
                api(b, "return api.updateBookingStatus(" + str(today_booking["id"]) + ",'checked_in');")
                check(
                    api(a, "return api.getBooking(" + str(today_booking["id"]) + ");")["status"]
                    == "checked_in",
                    "customer refresh reads host check-in from the same database booking",
                )
                api(b, "return api.updateBookingStatus(" + str(today_booking["id"]) + ",'completed');")
                api(
                    a,
                    "return api.addReview("
                    + str(stay["id"])
                    + ","
                    + json.dumps(
                        {
                            "bookingId": today_booking["id"],
                            "rating": 5,
                            "comment": "Verified shared database review",
                        }
                    )
                    + ");",
                )
                check(
                    any(
                        row["comment"] == "Verified shared database review"
                        for row in api(b, "return api.getReviews(" + str(stay["id"]) + ");")
                    ),
                    "review saved in one context is visible in another",
                )
                register(b, "other-host@example.com", "Other Host")
                other_app = api(b, "return api.applyHost(" + json.dumps(application_data) + ");")
                login(a, "shared-admin@example.com")
                api(a, "return api.decideHostApplication(" + str(other_app["id"]) + ",'approve');")
                login(b, "other-host@example.com")
                check(
                    api(
                        b,
                        "try{await api.getHostHomestay("
                        + str(stay["id"])
                        + ");return 200}catch(e){return e.status}",
                    )
                    in (403, 404),
                    "host B cannot read host A property",
                )
                actual_users = api(a, "return api.getAdminUsers();")
                with factory() as db:
                    stored_ids = set(db.scalars(select(User.id)))
                check(
                    {row["id"] for row in actual_users} == stored_ids and len(stored_ids) == 5,
                    "admin lists exactly the five database test accounts",
                )
                login(a, "huy@test.com")
                api(a, "return api.cancelBooking(" + str(booking["id"]) + ");")
                login(b, "shared-host@example.com")
                check(
                    next(
                        row
                        for row in api(b, "return api.getHostBookings();")
                        if str(row["id"]) == str(booking["id"])
                    )["status"]
                    == "cancelled",
                    "host refresh observes customer cancellation",
                )
                login(b, "huy@test.com")
                navigate(b, "booking-list.html", "!!document.querySelector('#booking-list .row')")
                check(
                    api(b, "return api.getBooking(" + str(booking["id"]) + ");")["status"] == "cancelled",
                    "second customer context reload sees cancellation from context A",
                )
                stop_process(server)
                server = start_server()
                navigate(a, "booking-list.html", "!!document.querySelector('#booking-list .row')")
                check(
                    any(
                        str(row["id"]) == str(booking["id"]) and row["status"] == "cancelled"
                        for row in api(a, "return api.getBookings();")
                    ),
                    "backend restart and frontend reload preserve database booking and session",
                )
                for tab in (a, b):
                    check(
                        tab.js(
                            "Object.entries("
                            + pollution
                            + ").every(([key,value])=>localStorage.getItem(key)===value)"
                        ),
                        "shared mode leaves local mock data untouched",
                    )
                    check(not tab.errors, "no uncaught browser errors during shared workflows")
                configuration = httpx.get(origin + "/js/runtime-config.js").text
                check(
                    "postgres" not in configuration.lower() and password not in configuration,
                    "browser runtime configuration contains no database credentials",
                )
                for route in ["gioi-thieu.html", "dieu-khoan.html", "lien-he.html"]:
                    navigate(
                        b,
                        route,
                        "!!document.querySelector('site-header header') && !!document.querySelector('main h1')",
                    )
                    check(
                        b.js(
                            "import('./js/config.js').then(config=>config.ACCOUNT_API_MODE && config.supportedApiRoute(location.pathname))"
                        ),
                        "shared deployment supports public page " + route,
                    )
                # Exercise the actual checkout UI in addition to the frontend adapter checks.
                login(a, "huy@test.com")
                navigate(
                    a,
                    f"detail.html?id={stay['id']}&checkin={payload['checkIn']}&checkout={payload['checkOut']}&adults=2&children=0",
                    "document.querySelector('.room-pick')?.disabled===false",
                )
                a.js("document.querySelector('.room-pick').click()")
                a.until("!document.querySelector('#book-btn').disabled")
                a.js("document.querySelector('#book-btn').click()")
                a.until("location.pathname.endsWith('/booking-page.html') && document.querySelector('#btnSubmit')?.disabled===false")
                a.js("(()=>{const original=window.fetch.bind(window);window.fetch=async(...args)=>{const response=await original(...args);if(new URL(args[0]).pathname==='/api/me/bookings' && args[1]?.method==='POST' && response.ok){window.checkoutReplyHeld=true;await new Promise(resolve=>{window.releaseCheckoutReply=resolve})}return response}})()")
                a.js("document.querySelector('#checkoutForm').requestSubmit()")
                a.until("window.checkoutReplyHeld===true")
                check(
                    a.js("location.pathname.endsWith('/booking-page.html') && document.querySelector('#btnSubmit').disabled"),
                    "checkout does not show success before receiving the backend confirmation",
                )
                a.js("window.releaseCheckoutReply()")
                a.until("location.pathname.endsWith('/booking-confirmed.html') && !!document.querySelector('#booking-server-state')")
                ui_booking_id = int(a.js("new URLSearchParams(location.search).get('id')"))
                with factory() as db:
                    check(db.get(Booking, ui_booking_id).customer_id == customer["id"], "checkout UI saved booking owned by the authenticated server user")
                login(b, "huy@test.com")
                navigate(b, "booking-list.html", "!!document.querySelector('#booking-list .row')")
                check(
                    any(str(row["id"]) == str(ui_booking_id) for row in api(b, "return api.getBookings();")),
                    "browser B reloads history with the booking submitted through browser A checkout UI",
                )
                navigate(a, f"booking-detail.html?id={ui_booking_id}", "!!document.querySelector('#bd-cancel')")
                a.js("document.querySelector('#bd-cancel').click()")
                a.until("document.querySelector('#confirm-dialog')?.open")
                a.js("document.querySelector('#confirm-dialog [data-confirm]').click()")
                a.until("document.querySelector('#bd-status')?.classList.contains('badge--danger')")
                b.call("Page.reload")
                b.until("!!document.querySelector('#booking-list .row')")
                check(api(b, "return api.getBooking(" + str(ui_booking_id) + ");")["status"] == "cancelled", "cancellation through browser A UI appears in browser B after reload")
                # Simulate API failure while frontend configuration and assets remain available.
                a.call("Network.setBlockedURLs", urls=["*/api/me/bookings*", "*/mock/*"])
                navigate(a, "booking-list.html", "!!document.querySelector('#booking-list .empty')")
                check(
                    a.js(
                        "!document.querySelector('#booking-list').textContent.includes('LOCAL-ONLY') && !document.querySelector('#booking-list .row')"
                    ),
                    "API network failure displays error without local/mock fallback",
                )
                b.js("import('./js/api.js').then(api=>{window.failureTestAPI=api})")
                stop_process(server)
                error = b.js(
                    "(async()=>{try{await window.failureTestAPI.getHostBookings();return 200}catch(e){return e.status}})()"
                )
                check(error == 0, "stopped backend returns connection error without mock fallback")
                report = {
                    "status": "PASS",
                    "count": len(checks),
                    "checks": checks,
                    "database": "isolated SQLite file" if sqlite else "isolated PostgreSQL schema",
                    "contexts": 2,
                    "physical_devices": False,
                    "lan_verified": False,
                    "internet_verified": False,
                }
                (ROOT / ("docs/LOCAL_SQLITE_BROWSER_RESULTS.json" if sqlite else "docs/SHARED_BROWSER_RESULTS.json")).write_text(
                    json.dumps(report, indent=2) + "\n", encoding="utf-8"
                )
                print(json.dumps(report))
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                stop_process(process)
        for connection in sockets:
            connection.close()
        engine.dispose()
        if admin_engine:
            with admin_engine.begin() as connection:
                assert schema.startswith("luxstay_shared_") and len(schema) == 39
                connection.execute(DropSchema(schema, cascade=True))
            admin_engine.dispose()
        if database_directory:
            database_directory.cleanup()


if __name__ == "__main__":
    main()
