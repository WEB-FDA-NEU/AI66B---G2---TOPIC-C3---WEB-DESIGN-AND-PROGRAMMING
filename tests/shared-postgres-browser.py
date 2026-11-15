"""Two isolated Chrome contexts, one real FastAPI and a dedicated PostgreSQL test schema."""

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


def main():
    url = make_url(os.environ.get("TEST_POSTGRES_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
        raise SystemExit("TEST_POSTGRES_URL must point to a dedicated PostgreSQL database ending in _test")
    browser = shutil.which("google-chrome") or os.path.join(
        os.environ.get("PROGRAMFILES", ""), "Google/Chrome/Application/chrome.exe"
    )
    if not Path(browser).is_file():
        raise SystemExit("Chrome is required")
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
            environment.update(
                APP_ENV="test",
                DATABASE_URL=database_url,
                JWT_SECRET=secrets.token_urlsafe(48),
                FRONTEND_MODE="shared",
                SERVE_FRONTEND="true",
                AUTH_RATE_LIMIT="1000",
                UPLOAD_DIR=str(work / "uploads"),
                CORS_ORIGINS=origin,
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
                customer = register(a, "shared-customer@example.com", "Shared Customer")
                remote = login(b, "shared-customer@example.com")
                with factory() as db:
                    check(
                        customer["id"]
                        == remote["id"]
                        == db.scalar(select(User.id).where(User.email == "shared-customer@example.com")),
                        "browser B logs in to browser A registered PostgreSQL user",
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
                    "admin context reads actual pending PostgreSQL application",
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
                            "name": "Shared PostgreSQL Stay",
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
                login(a, "shared-customer@example.com")
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
                    "guestEmail": "shared-customer@example.com",
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
                login(b, "shared-customer@example.com")
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
                    "window.originalHistoryFetch=window.fetch;window.fetch=async(...args)=>{const response=await originalHistoryFetch(...args);const url=String(args[0]);if(url.includes('/me/bookings?'))await new Promise(resolve=>setTimeout(resolve,url.includes('status=cancelled')?400:20));return response};document.querySelector('[data-filter=cancelled]').click();document.querySelector('[data-filter=all]').click()"
                )
                b.js("new Promise(resolve=>setTimeout(resolve,650))")
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
                        "PostgreSQL contains one booking and exactly two reserved nights",
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
                    "customer refresh reads host check-in from the same PostgreSQL booking",
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
                    {row["id"] for row in actual_users} == stored_ids and len(stored_ids) == 4,
                    "admin lists exactly the four PostgreSQL test accounts",
                )
                login(a, "shared-customer@example.com")
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
                server.terminate()
                server.wait(timeout=20)
                server = start_server()
                navigate(a, "booking-list.html", "!!document.querySelector('#booking-list .row')")
                check(
                    any(
                        str(row["id"]) == str(booking["id"]) and row["status"] == "cancelled"
                        for row in api(a, "return api.getBookings();")
                    ),
                    "backend restart and frontend reload preserve PostgreSQL booking and session",
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
                # Simulate API failure while frontend configuration and assets remain available.
                a.call("Network.setBlockedURLs", urls=["*/api/me/bookings*", "*/mock/*"])
                navigate(a, "booking-list.html", "!!document.querySelector('#booking-list .empty')")
                check(
                    a.js(
                        "!document.querySelector('#booking-list').textContent.includes('LOCAL-ONLY') && !document.querySelector('#booking-list .row')"
                    ),
                    "API network failure displays error without local/mock fallback",
                )
                server.terminate()
                server.wait(timeout=20)
                error = api(b, "try{await api.getHostBookings();return 200}catch(e){return e.status}")
                check(error == 0, "stopped backend returns connection error without mock fallback")
                report = {
                    "status": "PASS",
                    "count": len(checks),
                    "checks": checks,
                    "database": "isolated PostgreSQL schema",
                    "contexts": 2,
                    "physical_devices": False,
                    "lan_verified": False,
                    "internet_verified": False,
                }
                (ROOT / "docs/SHARED_BROWSER_RESULTS.json").write_text(
                    json.dumps(report, indent=2) + "\n", encoding="utf-8"
                )
                print(json.dumps(report))
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=20)
        for connection in sockets:
            connection.close()
        engine.dispose()
        with admin_engine.begin() as connection:
            assert schema.startswith("luxstay_shared_") and len(schema) == 39
            connection.execute(DropSchema(schema, cascade=True))
        admin_engine.dispose()


if __name__ == "__main__":
    main()
