"""Real Chrome/Edge fullstack acceptance with a disposable migrated test database.

No production database/profile/credential; Playwright is not installed, reuse local CDP.
python tests/api-accounts-browser.py
"""

import base64
import functools
import hashlib
import importlib.util
import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import httpx
from PIL import Image
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
# Direct script entry point: make this repository importable before backend imports.
sys.path.insert(0, str(ROOT))
from backend.database import make_engine, make_session_factory  # noqa: E402 - repository path bootstrap above
from backend.models import HostApplication, User  # noqa: E402 - repository path bootstrap above
from backend.security import hash_password  # noqa: E402 - repository path bootstrap above
from backend.tests.conftest import migrate  # noqa: E402 - repository path bootstrap above

spec = importlib.util.spec_from_file_location("ui_audit", ROOT / "tests/ui-browser.py")
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


class Browser(ui.CDP):
    def __init__(self, url):
        self.requests = []
        self.booking_attempts = []
        super().__init__(url)

    def receive(self):
        value = super().receive()
        if value.get("method") == "Network.requestWillBeSent":
            request = value["params"]["request"]
            from urllib.parse import urlsplit

            # Do not retain headers, body, token, password or query strings.
            self.requests.append((request["method"], urlsplit(request["url"]).path))
            if request["method"] == "POST" and urlsplit(request["url"]).path == "/api/me/bookings":
                key = next(
                    (v for k, v in request.get("headers", {}).items() if k.lower() == "idempotency-key"), ""
                )
                self.booking_attempts.append(
                    (
                        hashlib.sha256(key.encode()).hexdigest(),
                        hashlib.sha256(request.get("postData", "").encode()).hexdigest(),
                    )
                )
        return value


def main():
    browser = next(
        (
            p
            for p in [
                shutil.which("google-chrome"),
                os.path.join(os.environ.get("PROGRAMFILES", ""), "Google/Chrome/Application/chrome.exe"),
                os.path.join(
                    os.environ.get("PROGRAMFILES(X86)", ""), "Microsoft/Edge/Application/msedge.exe"
                ),
            ]
            if p and Path(p).is_file()
        ),
        None,
    )
    if not browser:
        raise RuntimeError("Installed Chrome or Edge required")
    parent = ROOT / "backend/.test-tmp"
    parent.mkdir(exist_ok=True)
    checks = []

    def check(value, label):
        if not value:
            raise AssertionError(label)
        checks.append(label)

    with tempfile.TemporaryDirectory(
        prefix="phase8-accounts-", dir=parent, ignore_cleanup_errors=True
    ) as temporary:
        work = Path(temporary).resolve()
        assert work.parent == parent.resolve()
        database_url = "sqlite:///" + (work / "browser.db").as_posix()
        password = secrets.token_urlsafe(24)
        changed = secrets.token_urlsafe(24)
        email = "browser-" + secrets.token_hex(5) + "@example.com"
        host_email = "host-" + secrets.token_hex(5) + "@example.com"
        admin_email = "admin-" + secrets.token_hex(5) + "@example.com"
        engine = make_engine(database_url)
        migrate(engine)
        factory = make_session_factory(engine)
        with factory() as db:
            db.add(
                User(
                    email=admin_email,
                    display_name="Test Admin",
                    password_hash=hash_password(password),
                    role="admin",
                )
            )
            db.commit()
        front = ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(ui.Handler, directory=str(ROOT / "frontend"))
        )
        threading.Thread(target=front.serve_forever, daemon=True).start()
        origin = f"http://127.0.0.1:{front.server_port}"
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        api_origin = f"http://127.0.0.1:{port}"
        environment = os.environ.copy()
        environment.update(
            APP_ENV="test",
            DATABASE_URL=database_url,
            JWT_SECRET=secrets.token_urlsafe(48),
            SERVE_FRONTEND="true",
            UPLOAD_DIR=str(work / "uploads"),
            AUTH_RATE_LIMIT="100",
            CORS_ORIGINS=f"{origin},http://localhost:{front.server_port}",
        )
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with (work / "server.log").open("w", encoding="utf-8") as log:
            server = subprocess.Popen(
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
            chrome = None
            try:
                client = httpx.Client(base_url=api_origin, timeout=15)
                for _ in range(100):
                    try:
                        if client.get("/api/ready").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.1)
                else:
                    raise RuntimeError("Test API did not start")
                profile = work / "chrome-profile"
                profile.mkdir()
                chrome = subprocess.Popen(
                    [
                        browser,
                        "--headless=new",
                        "--disable-gpu",
                        "--no-first-run",
                        "--remote-debugging-port=0",
                        "--user-data-dir=" + str(profile),
                        "--disable-background-networking",
                        "--host-resolver-rules=MAP fonts.googleapis.com ~NOTFOUND, MAP fonts.gstatic.com ~NOTFOUND",
                        "about:blank",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=flags,
                )
                active = profile / "DevToolsActivePort"
                for _ in range(100):
                    if active.exists():
                        break
                    time.sleep(0.1)
                debug_port = active.read_text().splitlines()[0]
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{debug_port}/json"))
                c = Browser(next(t["webSocketDebuggerUrl"] for t in tabs if t["type"] == "page"))
                c.call("Page.enable")
                c.call("Runtime.enable")
                c.call("Network.enable")
                c.call(
                    "Page.addScriptToEvaluateOnNewDocument",
                    source="globalThis.LUXSTAY_CONFIG=" + json.dumps({"apiBase": api_origin + "/api"}) + ";",
                )

                def page(path, ready):
                    c.call("Page.navigate", url=origin + "/" + path)
                    try:
                        c.until(
                            "location.pathname==="
                            + json.dumps("/" + path.split("?")[0])
                            + " && document.readyState==='complete' && ("
                            + ready
                            + ")"
                        )
                    except RuntimeError:
                        print(
                            json.dumps(
                                {
                                    "readiness_failure": path.split("?")[0],
                                    "runtime_errors": c.errors,
                                    "visible_notice": c.js("document.querySelector('#toast')?.textContent"),
                                    "review_state": c.js(
                                        "({visible:document.querySelector('#review-form-wrapper')?.hidden,form:!!document.querySelector('#review-form'),nameType:typeof document.querySelector('#review-form')?.name,notfound:document.querySelector('#detail-not-found')?.hidden})"
                                    ),
                                },
                                ensure_ascii=True,
                            )
                        )
                        raise

                def fill(selector, values):
                    c.js(
                        "(()=>{const f=document.querySelector("
                        + json.dumps(selector)
                        + ");const values="
                        + json.dumps(values)
                        + ";for(const [k,v] of Object.entries(values))f.elements.namedItem(k).value=v;})()"
                    )

                def submit(selector, double=False):
                    c.js(
                        "document.querySelector("
                        + json.dumps(selector)
                        + ").requestSubmit();"
                        + (
                            "document.querySelector(" + json.dumps(selector) + ").requestSubmit();"
                            if double
                            else ""
                        )
                    )

                def login(mail, secret):
                    page(
                        "login.html?accounts=api",
                        "!document.querySelector('#login-form [type=submit]').disabled",
                    )
                    fill("#login-form", {"email": mail, "password": secret})
                    submit("#login-form")
                    c.until(
                        "location.pathname.endsWith('/profile.html') && !document.querySelector('#profile-form [type=submit]').disabled"
                    )

                def api(expression):
                    return c.js("(async()=>{const m=await import('./js/api.js');" + expression + "})()")

                page(
                    "register.html?accounts=api",
                    "!document.querySelector('#register-form [type=submit]').disabled",
                )
                c.js(
                    "localStorage.setItem('app_user',JSON.stringify({id:99,role:'admin',display_name:'Mock Admin'}));localStorage.setItem('app_token','mock-token');localStorage.setItem('customerBookings','[\"sentinel\"]')"
                )
                name = '<img src=x onerror="globalThis.accountXss=1">'
                fill(
                    "#register-form",
                    {
                        "display_name": name,
                        "email": email,
                        "phone": "0912345678",
                        "password": password,
                        "confirm": password,
                    },
                )
                submit("#register-form", True)
                c.until(
                    "location.pathname.endsWith('/profile.html') && !document.querySelector('#profile-form [type=submit]').disabled"
                )
                check(
                    sum(m == "POST" and p == "/api/auth/register" for m, p in c.requests) == 1,
                    "double submit sends one registration",
                )
                check(
                    c.js("document.querySelector('#profile-summary-name').textContent") == name,
                    "server user data rendered as text",
                )
                check(
                    c.js("!globalThis.accountXss && !document.querySelector('#profile-summary-name img')"),
                    "account HTML injection does not execute",
                )
                check(
                    c.js(
                        "!localStorage.getItem('luxstay_api_access_token') && !!sessionStorage.getItem('luxstay_api_access_token')"
                    ),
                    "API bearer scoped to sessionStorage",
                )
                c.js(
                    "const forged=JSON.parse(sessionStorage.getItem('luxstay_api_user'));forged.role='admin';sessionStorage.setItem('luxstay_api_user',JSON.stringify(forged))"
                )
                check(
                    api("return (await m.getProfile()).role==='user'"),
                    "server profile overwrites forged cached role",
                )
                check(
                    c.js(
                        "!JSON.stringify([localStorage,sessionStorage]).includes("
                        + json.dumps(password)
                        + ")"
                    ),
                    "no raw API password persisted",
                )
                check(
                    c.js("localStorage.getItem('customerBookings')==='[\"sentinel\"]'"),
                    "API page does not reset business mock storage",
                )
                check(
                    api("try{await m.createBooking({});return false}catch(e){return e.status===503}"),
                    "unintegrated business is blocked without mock write",
                )
                fill("#profile-form", {"display_name": "Updated Browser User"})
                submit("#profile-form")
                c.until(
                    "document.querySelector('#profile-summary-name').textContent==='Updated Browser User' && !document.querySelector('#profile-form [type=submit]').disabled"
                )
                c.call("Page.reload")
                c.until(
                    "document.querySelector('#profile-summary-name')?.textContent==='Updated Browser User'"
                )
                check(True, "profile persists through API and reload")
                bad = work / "invalid.txt"
                bad.write_text("not an image")
                png = work / "avatar.png"
                Image.new("RGB", (8, 8), "blue").save(png)
                root = c.call("DOM.getDocument")["root"]["nodeId"]
                node = c.call("DOM.querySelector", nodeId=root, selector="#avatar")["nodeId"]
                c.call("DOM.setFileInputFiles", nodeId=node, files=[str(bad)])
                c.until("!!document.querySelector('#avatar-error').textContent")
                check(True, "invalid avatar type rejected in browser")
                c.call("DOM.setFileInputFiles", nodeId=node, files=[str(png)])
                c.until(
                    "document.querySelector('#avatar-preview').src.startsWith('data:image/') && !document.querySelector('#profile-form [type=submit]').disabled"
                )
                submit("#profile-form")
                c.until(
                    "document.querySelector('#avatar-preview').src.includes('/uploads/') && document.querySelector('#avatar-preview').naturalWidth>0"
                )
                check(
                    c.js(
                        'document.querySelector("#avatar-preview").src.startsWith('
                        + json.dumps(api_origin)
                        + ")"
                    ),
                    "avatar path uses API origin across ports",
                )
                check(
                    c.js(
                        "import('./js/config.js').then(m=>m.safeImageURL('javascript:alert(1)')==='img/placeholder.svg')"
                    ),
                    "unsafe avatar protocol is rejected",
                )
                for width in [1440, 1024, 768, 375]:
                    c.call(
                        "Emulation.setDeviceMetricsOverride",
                        width=width,
                        height=950,
                        deviceScaleFactor=1,
                        mobile=False,
                    )
                    check(
                        c.js("document.documentElement.scrollWidth<=innerWidth+1"),
                        f"account profile no horizontal overflow at {width}px",
                    )
                fill(
                    "#password-form",
                    {"current_password": password, "new_password": changed, "confirm_password": changed},
                )
                submit("#password-form")
                c.until(
                    "location.pathname.endsWith('/login.html') && !sessionStorage.getItem('luxstay_api_access_token') && document.readyState==='complete' && document.querySelector('#login-form [type=submit]')?.disabled===false"
                )
                check(
                    "password=" not in c.js("location.href"),
                    "password change revokes session without URL credentials",
                )
                fill("#login-form", {"email": email, "password": password})
                submit("#login-form")
                c.until(
                    "document.querySelector('#login-form [name=password]')?.getAttribute('aria-invalid')==='true'"
                )
                check(True, "old password login failure maps to visible field error")
                login(email, changed)
                page(
                    "host-register.html?accounts=api",
                    "!document.querySelector('#host-register-form [type=submit]').disabled",
                )
                check(
                    c.js("document.querySelector('[name=password]').closest('.field').hidden"),
                    "existing customer applies without reentering credentials",
                )
                submit("#host-register-form")
                c.until(
                    "location.pathname.endsWith('/profile.html') && !!document.querySelector('#host-application-status')?.textContent"
                )
                check(
                    c.js(
                        "document.querySelector('#become-host-section a').getAttribute('aria-disabled')==='true'"
                    ),
                    "host pending shown; no automatic host role",
                )
                # Test harness approves via real API; admin UI remains outside this module gate.
                admin = client.post(
                    "/api/auth/login", json={"email": admin_email, "password": password}
                ).json()
                with factory() as db:
                    uid = db.scalar(select(User.id).where(User.email == email))
                    application = db.scalar(select(HostApplication).where(HostApplication.user_id == uid))
                    aid = application.id
                check(
                    client.post(
                        f"/api/admin/host-applications/{aid}/approve",
                        headers={"Authorization": "Bearer " + admin["access_token"]},
                    ).status_code
                    == 200,
                    "real approval persisted in test database",
                )
                c.call("Page.reload")
                c.until("location.pathname.endsWith('/login.html')")
                login(email, changed)
                check(
                    c.js("JSON.parse(sessionStorage.getItem('luxstay_api_user')).role==='host'"),
                    "revoked session requires login and server supplies approved role",
                )
                token = c.js("sessionStorage.getItem('luxstay_api_access_token')")
                c.call("Network.setBlockedURLs", urls=[api_origin + "/api/auth/logout"])
                c.js(
                    "document.querySelector('#toast').textContent='';document.querySelector('[data-action=logout]').click()"
                )
                c.until("!!document.querySelector('#toast').textContent")
                check(
                    c.js(
                        "!!sessionStorage.getItem('luxstay_api_access_token') && location.pathname.endsWith('/profile.html')"
                    ),
                    "failed logout retains session for server revocation retry",
                )
                c.call("Network.setBlockedURLs", urls=[])
                c.js("document.querySelector('[data-action=logout]').click()")
                c.until(
                    "location.pathname.endsWith('/login.html') && !sessionStorage.getItem('luxstay_api_access_token') && document.readyState==='complete' && document.querySelector('#login-form [type=submit]')?.disabled===false"
                )
                check(
                    client.get("/api/me", headers={"Authorization": "Bearer " + token}).status_code == 401,
                    "browser logout revokes server session",
                )
                page(
                    "host-register.html?accounts=api",
                    "!document.querySelector('#host-register-form [type=submit]').disabled",
                )
                fill(
                    "#host-register-form",
                    {
                        "display_name": "New Host Applicant",
                        "email": host_email,
                        "phone": "0912345678",
                        "password": password,
                        "confirm": password,
                    },
                )
                submit("#host-register-form")
                c.until(
                    "location.pathname.endsWith('/profile.html') && !!document.querySelector('#host-application-status')?.textContent"
                )
                check(
                    c.js("JSON.parse(sessionStorage.getItem('luxstay_api_user')).role==='user'"),
                    "new host registration creates customer plus pending application",
                )
                page("booking-page.html?accounts=api", "!!document.querySelector('main .empty')")
                check(
                    c.js("!document.querySelector('#checkoutForm')"),
                    "unsupported API route fails closed instead of local booking/card form",
                )
                # localhost hostname uses a separate browser storage origin and the same real backend.
                origin = f"http://localhost:{front.server_port}"
                login(host_email, password)
                check(
                    c.js(
                        "document.querySelector('#profile-summary-name').textContent==='New Host Applicant'"
                    ),
                    "localhost + cross-origin CORS API works",
                )
                check(not c.errors, "no uncaught JavaScript or console.error in account flows")
                check(
                    not any("password" in p.lower() for _, p in c.requests if p.endswith(".html")),
                    "no password query/form GET navigation",
                )
                # The next module uses DB fixtures created through existing management APIs.
                from datetime import timedelta

                from backend.booking_service import business_today
                from backend.models import Booking

                host_session = client.post(
                    "/api/auth/login", json={"email": email, "password": changed}
                ).json()
                host_header = {"Authorization": "Bearer " + host_session["access_token"]}
                stays = []
                for index in range(2):
                    stay_response = client.post(
                        "/api/host/homestays",
                        json={
                            "name": f"Live Stay {index}",
                            "address": "Da Lat, Viet Nam",
                            "description": "Actual database property",
                            "images": ["img/placeholder.svg"],
                        },
                        headers=host_header,
                    )
                    assert stay_response.status_code == 201
                    stay_data = stay_response.json()
                    room_response = client.post(
                        "/api/host/rooms",
                        json={
                            "homestayId": stay_data["id"],
                            "name": f"Real Room {index}",
                            "description": "Database room description",
                            "capacity": 2,
                            "inventory": 1,
                            "pricePerNight": 123456,
                            "images": ["img/placeholder.svg"],
                        },
                        headers=host_header,
                    )
                    assert room_response.status_code == 201
                    stays.append((stay_data, room_response.json()))
                sid = stays[0][0]["id"]
                ci = (business_today() + timedelta(days=10)).isoformat()
                co = (business_today() + timedelta(days=12)).isoformat()
                c.call(
                    "Emulation.setDeviceMetricsOverride",
                    width=1440,
                    height=950,
                    deviceScaleFactor=1,
                    mobile=False,
                )
                page("index.html?mode=api", "document.querySelectorAll('#hero-slides article').length===2")
                c.js("localStorage.setItem('customerBookings','[\"api-sentinel\"]')")
                page("?mode=api", "document.querySelectorAll('#hero-slides article').length===2")
                check(True, "API mode supports the root index route as well as index.html")
                first_slide = c.js("document.querySelector('#hero-slides .is-active').dataset.id")
                time.sleep(2.3)
                check(
                    c.js("document.querySelector('#hero-slides .is-active').dataset.id") != first_slide,
                    "database carousel automatically advances after two seconds",
                )
                page(
                    "search.html?mode=api&q=Live+Stay+0",
                    "document.querySelectorAll('#results .card').length===1",
                )
                check(
                    c.js("document.querySelector('.card__link').href.includes('mode=api')"),
                    "search backend filter and card mode are preserved",
                )
                page(
                    f"detail.html?mode=api&id={sid}&checkin={ci}&checkout={co}&adults=2&children=0",
                    "document.querySelector('.room-pick') && !document.querySelector('.room-pick').disabled",
                )
                check(
                    c.js(
                        "document.querySelectorAll('.room-card').length===1 && document.querySelector('.room-card__name').textContent==='Real Room 0'"
                    ),
                    "detail uses the actual RoomType without invented Deluxe",
                )
                c.js("document.querySelector('.room-pick').click()")
                c.until("!document.querySelector('#book-btn').disabled")
                check(
                    c.js(
                        "document.querySelector('#summary-total').textContent===new Intl.NumberFormat('vi-VN',{style:'currency',currency:'VND',maximumFractionDigits:0}).format(259258)"
                    ),
                    "quote and rounded service fee come from backend",
                )
                c.js("document.querySelector('#book-btn').click()")
                c.until(
                    "location.pathname.endsWith('/booking-page.html') && !document.querySelector('#btnSubmit').disabled"
                )
                check(
                    c.js("!document.querySelector('#cardNum,#cardCvv,#cardExp')"),
                    "API checkout collects no PAN or CVV",
                )
                c.js(
                    "(()=>{const original=window.fetch.bind(window);window.fetch=async(...args)=>{const response=await original(...args);if(!window.lostBookingReply && new URL(args[0]).pathname==='/api/me/bookings' && args[1]?.method==='POST'){window.lostBookingReply=true;throw new TypeError('Injected lost response after commit');}return response;};})()"
                )
                submit("#checkoutForm", True)
                c.until(
                    "!document.querySelector('#formMsg').hidden && !document.querySelector('#btnSubmit').disabled"
                )
                with factory() as db:
                    customer_id = db.scalar(select(User.id).where(User.email == host_email))
                    saved = list(db.scalars(select(Booking).where(Booking.customer_id == customer_id)))
                    assert len(saved) == 1
                    bid = saved[0].id
                check(True, "lost response after server commit created only one booking")
                c.call("Page.reload")
                c.until(
                    "!document.querySelector('#btnSubmit')?.disabled && !document.querySelector('#formMsg').hidden"
                )
                submit("#checkoutForm")
                c.until(
                    "location.pathname.endsWith('/booking-confirmed.html') && !!document.querySelector('#booking-server-state')"
                )
                check(
                    len(c.booking_attempts) == 2 and len(set(c.booking_attempts)) == 1,
                    "retry after reload keeps identical idempotency key and payload",
                )
                check(
                    c.js(
                        "document.querySelector('.booking-confirmed-code-card .badge').textContent"
                    ).startswith("\u0043h\u1edd"),
                    "confirmation shows pending, not confirmed or bank paid",
                )
                check(
                    c.js(
                        "!sessionStorage.getItem('lastBooking') && localStorage.customerBookings==='[\"api-sentinel\"]'"
                    ),
                    "booking source is DB, not local business records",
                )
                c.call("Page.reload")
                c.until("!!document.querySelector('#booking-server-state')")
                check(
                    c.js("document.querySelector('#bCode').textContent.startsWith('BK')"),
                    "confirmation reload fetches persisted booking",
                )
                check(
                    client.patch(
                        f"/api/host/bookings/{bid}/status", json={"status": "confirmed"}, headers=host_header
                    ).status_code
                    == 200,
                    "host API confirms the same customer booking",
                )
                page(
                    f"booking-detail.html?mode=api&id={bid}",
                    "document.querySelector('#bd-status')?.classList.contains('badge--success')",
                )
                check(
                    c.js("!!document.querySelector('#booking-payment-state')"),
                    "customer reads shared booking state and actual pending payment",
                )
                c.js("document.querySelector('#bd-cancel').click()")
                c.until("document.querySelector('#confirm-dialog')?.open")
                c.js("document.querySelector('#confirm-dialog [data-confirm]').click()")
                c.until("document.querySelector('#bd-status')?.classList.contains('badge--danger')")
                with factory() as db:
                    check(
                        db.get(Booking, bid).status == "cancelled",
                        "customer cancellation is committed to shared DB",
                    )
                page("booking-list.html?mode=api", "!!document.querySelector('#booking-list .row')")
                check(
                    c.js("document.querySelector('#booking-list .row').dataset.status==='cancelled'"),
                    "booking history is server data after cancellation",
                )
                assert (
                    client.post(
                        f"/api/host/rooms/{stays[0][1]['id']}/blocks",
                        json={"start_date": ci, "end_date": co},
                        headers=host_header,
                    ).status_code
                    == 201
                )
                page(
                    f"detail.html?mode=api&id={sid}&checkin={ci}&checkout={co}",
                    "document.querySelector('.room-pick')?.disabled===true",
                )
                check(
                    c.js("document.querySelector('#book-btn').disabled"),
                    "host block disables customer booking through backend availability",
                )
                login(email, changed)
                page(
                    "host-bookings.html?mode=api",
                    "document.body.hasAttribute('data-guard-ok') && !!document.querySelector('#list .host-booking-card')",
                )
                check(
                    c.js("document.querySelector('#list .badge').textContent").startswith(
                        "\u0110\u00e3 h\u1ee7y"
                    ),
                    "host browser reads customer cancellation from shared DB",
                )
                for width in [1440, 1024, 768, 375]:
                    c.call(
                        "Emulation.setDeviceMetricsOverride",
                        width=width,
                        height=950,
                        deviceScaleFactor=1,
                        mobile=width == 375,
                    )
                    check(
                        c.js("document.documentElement.scrollWidth<=innerWidth"),
                        "host booking layout without horizontal overflow " + str(width),
                    )
                # A separate pending booking for actual host UI approval/rejection.
                user_session = client.post(
                    "/api/auth/login", json={"email": host_email, "password": password}
                ).json()
                user_header = {"Authorization": "Bearer " + user_session["access_token"]}
                other_stay, other_room = stays[1]
                payload = {
                    "homestayId": other_stay["id"],
                    "checkIn": ci,
                    "checkOut": co,
                    "adults": 1,
                    "children": 0,
                    "rooms": [{"key": other_room["key"], "qty": 1}],
                    "guestName": '<img src=x onerror="globalThis.hostXss=1">',
                    "guestEmail": host_email,
                }
                pending = client.post(
                    "/api/me/bookings",
                    json=payload,
                    headers={**user_header, "Idempotency-Key": secrets.token_urlsafe(24)},
                )
                assert pending.status_code == 201
                pending_id = pending.json()["id"]
                page("host-bookings.html?mode=api", "!!document.querySelector('#list [data-act]')")
                check(
                    c.js(
                        "!globalThis.hostXss && !document.querySelector('.host-booking-info img') && document.querySelector('.host-booking-info').textContent.includes('<img')"
                    ),
                    "host guest name is text, not executable HTML",
                )
                c.js("document.querySelector('[data-status=pending]').click()")
                c.until("document.querySelectorAll('#list .host-booking-card').length===1")
                c.js(
                    "document.querySelector('#list [data-act]').click();document.querySelector('#list [data-act]').click()"
                )
                c.until("!document.querySelector('#list [data-act]')")
                with factory() as db:
                    check(
                        db.get(Booking, pending_id).status == "confirmed",
                        "host UI confirms once and refreshes server-filtered pending list",
                    )
                c.js("document.querySelector('[data-status=confirmed]').click()")
                c.until("!!document.querySelector('#list [data-act]')")
                check(
                    c.js("document.querySelector('#list .badge').textContent").startswith(
                        "\u0110\u00e3 x\u00e1c"
                    ),
                    "host status tab fetches real confirmed bookings",
                )
                page(
                    f"host-rooms.html?mode=api&homestayId={sid}",
                    "!!document.querySelector('#hsSwitch option') && !!document.querySelector('.host-room-card')",
                )
                c.js("document.querySelector('#addBtn').click()")
                c.until(
                    "document.querySelector('#roomForm').classList.contains('is-open') && !document.querySelector('#roomForm [type=submit]').disabled"
                )
                c.js(
                    "document.querySelector('#rName').value='Browser Room';document.querySelector('#rDesc').value='Browser inventory and partial blocks';document.querySelector('#rCap').value=3;document.querySelector('#rPrice').value=234567;document.querySelector('#rInventory').value=2"
                )
                root = c.call("DOM.getDocument")["root"]["nodeId"]
                image_node = c.call("DOM.querySelector", nodeId=root, selector="#rImages")["nodeId"]
                c.call("DOM.setFileInputFiles", nodeId=image_node, files=[str(png)])
                c.until(
                    "document.querySelector('#rPreview img')?.src.includes('/uploads/') && !document.querySelector('#roomForm [type=submit]').disabled"
                )
                check(
                    c.js("document.querySelector('#rPreview img').naturalWidth>0"),
                    "room upload preview uses real backend image across origins",
                )
                submit("#roomForm", True)
                c.until(
                    "!document.querySelector('#roomForm').classList.contains('is-open') && document.querySelectorAll('.host-room-card').length===2"
                )
                with factory() as db:
                    from backend.models import Room, RoomBlock

                    created_room = db.scalar(select(Room).where(Room.name == "Browser Room"))
                    assert created_room is not None and created_room.inventory == 2
                    room_id = created_room.id
                check(True, "host browser creates actual room with inventory and positive price")
                c.js("document.querySelector('[data-edit=\"" + str(room_id) + "\"]').click()")
                c.until(
                    "document.querySelector('#roomId').value==='"
                    + str(room_id)
                    + "' && !document.querySelector('#addBlockDate').disabled"
                )
                c.js(
                    "document.querySelector('#rBlockDate').value="
                    + json.dumps(ci)
                    + ";document.querySelector('#rBlockEnd').value="
                    + json.dumps(co)
                    + ";document.querySelector('#rBlockUnit').value='1';document.querySelector('#rBlockReason').value='<img src=x onerror=globalThis.blockXss=1>';document.querySelector('#addBlockDate').click()"
                )
                c.until(
                    "document.querySelectorAll('#blockList [data-block-id]').length===1 && !document.querySelector('#addBlockDate').disabled"
                )
                check(
                    c.js("!globalThis.blockXss && !document.querySelector('#blockList img')"),
                    "partial block reason is safe text",
                )
                c.js("document.querySelector('#rName').value='Browser Room Edited'")
                submit("#roomForm")
                c.until(
                    "!document.querySelector('#roomForm').classList.contains('is-open') && document.querySelector('#list').textContent.includes('Browser Room Edited')"
                )
                with factory() as db:
                    records = list(db.scalars(select(RoomBlock).where(RoomBlock.room_id == room_id)))
                    check(
                        len(records) == 1 and records[0].unit == 1,
                        "room metadata save preserves partial-unit block",
                    )
                availability = client.get(
                    f"/api/items/{sid}/availability", params={"checkin": ci, "checkout": co, "adults": 1}
                ).json()
                check(
                    next(row for row in availability["rooms"] if str(row["id"]) == str(room_id))["available"]
                    == 1,
                    "customer availability reflects remaining unblocked inventory",
                )
                c.js("document.querySelector('[data-edit=\"" + str(room_id) + "\"]').click()")
                c.until(
                    "document.querySelectorAll('#blockList [data-block-id]').length===1 && !document.querySelector('#addBlockDate').disabled"
                )
                c.js(
                    "document.querySelector('#blockList button').click();document.querySelector('#rBlockReason').value='Edited partial block';document.querySelector('#addBlockDate').click()"
                )
                c.until(
                    "document.querySelector('#blockList').textContent.includes('Edited partial block') && !document.querySelector('#addBlockDate').disabled"
                )
                check(True, "host browser updates structured block through PUT")
                for width in [1440, 1024, 768, 375]:
                    c.call(
                        "Emulation.setDeviceMetricsOverride",
                        width=width,
                        height=950,
                        deviceScaleFactor=1,
                        mobile=width == 375,
                    )
                    check(
                        c.js("document.documentElement.scrollWidth<=innerWidth"),
                        "host room form without horizontal overflow " + str(width),
                    )
                    screenshot = c.call("Page.captureScreenshot", format="png", captureBeyondViewport=False)
                    (parent / f"phase9-host-room-{width}.png").write_bytes(
                        base64.b64decode(screenshot["data"])
                    )
                c.js("document.querySelectorAll('#blockList button')[1].click()")
                c.until("document.querySelector('#confirm-dialog').open")
                c.js("document.querySelector('#confirm-dialog [data-confirm]').click()")
                c.until(
                    "document.querySelectorAll('#blockList [data-block-id]').length===0 && !document.querySelector('#addBlockDate').disabled"
                )
                with factory() as db:
                    check(
                        db.scalar(select(RoomBlock.id).where(RoomBlock.room_id == room_id)) is None,
                        "host browser removes only selected structured block",
                    )
                c.js(
                    "document.querySelector('#rBlockDate').value="
                    + json.dumps(ci)
                    + ";document.querySelector('#rBlockEnd').value="
                    + json.dumps(co)
                    + ";document.querySelector('#rBlockUnit').value='';document.querySelector('#rBlockReason').value='All-unit maintenance';document.querySelector('#addBlockDate').click()"
                )
                c.until(
                    "document.querySelectorAll('#blockList [data-block-id]').length===1 && !document.querySelector('#addBlockDate').disabled"
                )
                all_availability = client.get(
                    f"/api/items/{sid}/availability", params={"checkin": ci, "checkout": co, "adults": 1}
                ).json()
                check(
                    next(row for row in all_availability["rooms"] if str(row["id"]) == str(room_id))[
                        "available"
                    ]
                    == 0,
                    "host all-unit block removes every unit from customer availability",
                )
                c.js(
                    "document.querySelector('#cancelRoomForm').click();document.querySelector('[data-del=\""
                    + str(room_id)
                    + "\"]').click()"
                )
                c.until("document.querySelector('#confirm-dialog').open")
                c.js("document.querySelector('#confirm-dialog [data-confirm]').click()")
                c.until("document.querySelectorAll('.host-room-card').length===1")
                with factory() as db:
                    check(
                        db.get(Room, room_id).status == "deleted", "room delete preserves record and history"
                    )
                # Reject a separate stay, then verify the recorded reason from the browser.
                reject_payload = {
                    **payload,
                    "checkIn": (business_today() + timedelta(days=20)).isoformat(),
                    "checkOut": (business_today() + timedelta(days=21)).isoformat(),
                }
                reject_booking = client.post(
                    "/api/me/bookings",
                    json=reject_payload,
                    headers={**user_header, "Idempotency-Key": secrets.token_urlsafe(24)},
                )
                assert reject_booking.status_code == 201
                reject_id = reject_booking.json()["id"]
                page("host-bookings.html?mode=api", "!!document.querySelector('#list [data-reject]')")
                c.js("document.querySelector('#list [data-reject]').click()")
                c.until("document.querySelector('#reject-dialog').open")
                c.js(
                    "document.querySelector('#rejectReason').value='<svg onload=globalThis.rejectXss=1>';document.querySelector('#rejectConfirm').click()"
                )
                c.until(
                    "!document.querySelector('#reject-dialog').open && !!document.querySelector('.host-booking-reject-reason:not([hidden])')"
                )
                with factory() as db:
                    check(db.get(Booking, reject_id).status == "rejected", "host UI rejection persists in DB")
                check(
                    c.js(
                        "!globalThis.rejectXss && !document.querySelector('.host-booking-reject-reason svg')"
                    ),
                    "rejection reason renders as plain text",
                )
                page(
                    "host-homestay-form.html?mode=api",
                    "!document.querySelector('#form [type=submit]').disabled",
                )
                hostile_stay = "<img src=x onerror=globalThis.stayXss=1>"
                fill(
                    "#form",
                    {
                        "name": hostile_stay,
                        "address": "Hue, Viet Nam",
                        "description": "Created by actual host browser UI",
                    },
                )
                submit("#form", True)
                c.until(
                    "location.pathname.endsWith('/host-homestays.html') && document.querySelectorAll('.host-homestay-card').length===3"
                )
                check(
                    c.js(
                        "!globalThis.stayXss && [...document.querySelectorAll('.row__title')].some(el=>el.textContent.startsWith('<img'))"
                    ),
                    "host property created once and title is safe text",
                )
                with factory() as db:
                    from backend.models import Homestay

                    created = db.scalar(select(Homestay).where(Homestay.name == hostile_stay))
                    assert created is not None
                    created_id = created.id
                page(
                    f"host-homestay-form.html?mode=api&id={created_id}",
                    "!document.querySelector('#form [type=submit]').disabled && document.querySelector('#name').value.startsWith('<img')",
                )
                fill("#form", {"name": "Edited browser stay", "address": "Hue, Thua Thien Hue"})
                submit("#form")
                c.until(
                    "location.pathname.endsWith('/host-homestays.html') && document.querySelector('#list')?.textContent.includes('Edited browser stay')"
                )
                c.call("Page.reload")
                c.until("document.querySelector('#list')?.textContent.includes('Edited browser stay')")
                check(True, "host homestay edit survives list reload from DB")
                with factory() as db:
                    edited_stay = db.get(Homestay, created_id)
                    check(
                        edited_stay.location == "Hue, Thua Thien Hue"
                        and edited_stay.city == "Thua Thien Hue",
                        "host address edit refreshes catalog location instead of retaining stale city",
                    )
                for width in [1440, 1024, 768, 375]:
                    c.call(
                        "Emulation.setDeviceMetricsOverride",
                        width=width,
                        height=950,
                        deviceScaleFactor=1,
                        mobile=width == 375,
                    )
                    check(
                        c.js("document.documentElement.scrollWidth<=innerWidth"),
                        "host property layout without horizontal overflow " + str(width),
                    )
                c.js(
                    "[...document.querySelectorAll('.host-homestay-card')].find(el=>el.textContent.includes('Edited browser stay')).querySelector('[data-del]').click()"
                )
                c.until("document.querySelector('#confirm-dialog').open")
                c.js("document.querySelector('#confirm-dialog [data-confirm]').click()")
                c.until("document.querySelectorAll('.host-homestay-card').length===2")
                with factory() as db:
                    check(
                        db.get(Homestay, created_id).status == "deleted",
                        "host delete is a persisted soft delete",
                    )
                login(host_email, password)
                c.js(
                    "sessionStorage.setItem('luxstay_api_user',JSON.stringify({id:1,role:'host',display_name:'Forged'}))"
                )
                page(
                    "host-bookings.html?mode=api",
                    "document.body.hasAttribute('data-guard-ok') && !!document.querySelector('main .empty')",
                )
                check(
                    c.js(
                        "!document.querySelector('#list [data-act]') && JSON.parse(sessionStorage.getItem('luxstay_api_user')).role==='user'"
                    ),
                    "host guard reloads backend role and rejects forged cache",
                )
                login(email, changed)
                page(
                    "host-dashboard.html?mode=api",
                    "document.querySelector('#period-note').textContent.includes('kh\u00f4ng ph\u1ea3i giao d\u1ecbch')",
                )
                check(
                    c.js("document.querySelector('#kpi-revenue').nextElementSibling.textContent").startswith(
                        "Gi\u00e1 tr\u1ecb"
                    ),
                    "host dashboard labels booking value separately from captured cash",
                )
                check(
                    c.js("!!document.querySelector('#recent .host-dashboard-booking-row')"),
                    "host dashboard recent bookings use shared server snapshots",
                )
                today = business_today()
                arrival_payload = {
                    **payload,
                    "checkIn": today.isoformat(),
                    "checkOut": (today + timedelta(days=1)).isoformat(),
                    "guestName": "Arrival Browser Guest",
                }
                arrival = client.post(
                    "/api/me/bookings",
                    json=arrival_payload,
                    headers={**user_header, "Idempotency-Key": secrets.token_urlsafe(24)},
                )
                assert arrival.status_code == 201
                arrival_id = arrival.json()["id"]
                assert (
                    client.patch(
                        f"/api/host/bookings/{arrival_id}/status",
                        json={"status": "confirmed"},
                        headers=host_header,
                    ).status_code
                    == 200
                )
                page(
                    "host-bookings.html?mode=api",
                    "!!document.querySelector('[data-act=\"" + str(arrival_id) + ":checked_in\"]')",
                )
                c.js("document.querySelector('[data-act=\"" + str(arrival_id) + ":checked_in\"]').click()")
                c.until("!!document.querySelector('[data-act=\"" + str(arrival_id) + ":completed\"]')")
                with factory() as db:
                    check(
                        db.get(Booking, arrival_id).status == "checked_in",
                        "host browser check-in obeys current business date",
                    )
                historic_payload = {
                    **payload,
                    "checkIn": (today + timedelta(days=25)).isoformat(),
                    "checkOut": (today + timedelta(days=26)).isoformat(),
                    "guestName": "Completed Browser Guest",
                }
                historic = client.post(
                    "/api/me/bookings",
                    json=historic_payload,
                    headers={**user_header, "Idempotency-Key": secrets.token_urlsafe(24)},
                )
                assert historic.status_code == 201
                completed_id = historic.json()["id"]
                assert (
                    client.patch(
                        f"/api/host/bookings/{completed_id}/status",
                        json={"status": "confirmed"},
                        headers=host_header,
                    ).status_code
                    == 200
                )
                # Explicit historical fixture on disposable test DB only; no production clock or API bypass.
                from datetime import datetime, timezone

                from backend.models import BookingStatusHistory, Review, RoomNight

                with factory() as db:
                    historical = db.get(Booking, completed_id)
                    historical.check_in = today - timedelta(days=1)
                    historical.check_out = today
                    historical.status = "checked_in"
                    for night in db.scalars(select(RoomNight).where(RoomNight.booking_id == completed_id)):
                        night.night = today - timedelta(days=1)
                    db.add(
                        BookingStatusHistory(
                            booking_id=completed_id,
                            old_status="confirmed",
                            new_status="checked_in",
                            changed_by=historical.customer_id,
                            reason="Historical fixture in isolated browser test DB",
                            changed_at=datetime.now(timezone.utc),
                        )
                    )
                    db.commit()
                page(
                    "host-bookings.html?mode=api",
                    "!!document.querySelector('[data-act=\"" + str(completed_id) + ":completed\"]')",
                )
                c.js("document.querySelector('[data-act=\"" + str(completed_id) + ":completed\"]').click()")
                c.until("!document.querySelector('[data-act=\"" + str(completed_id) + ":completed\"]')")
                with factory() as db:
                    check(
                        db.get(Booking, completed_id).status == "completed",
                        "host browser completes eligible historical booking fixture",
                    )
                page(
                    f"host-rooms.html?mode=api&homestayId={other_stay['id']}",
                    "!!document.querySelector('.host-room-card')",
                )
                c.js("document.querySelector('[data-edit=\"" + str(other_room["id"]) + "\"]').click()")
                c.until(
                    "document.querySelector('#roomForm').classList.contains('is-open') && !document.querySelector('#roomForm [type=submit]').disabled"
                )
                c.js("document.querySelector('#rPrice').value=345678")
                submit("#roomForm")
                c.until(
                    "!document.querySelector('#roomForm').classList.contains('is-open') && document.querySelector('#list').textContent.includes('345.678')"
                )
                original_booking = client.get(f"/api/me/bookings/{pending_id}", headers=user_header).json()
                check(
                    original_booking["rooms"][0]["pricePerNight"] == 123456
                    and original_booking["totalPrice"] == 259258,
                    "host UI price update preserves existing booking snapshot",
                )
                login(host_email, password)
                page(
                    f"detail.html?mode=api&id={other_stay['id']}&review=1&bookingId={completed_id}",
                    "document.querySelector('#review-form-wrapper')?.hidden===false",
                )
                fill(
                    "#review-form",
                    {
                        "name": "Spoofed Author",
                        "rating": "5",
                        "comment": "<img src=x onerror=globalThis.reviewXss=1> verified stay",
                    },
                )
                submit("#review-form", True)
                c.until(
                    "document.querySelectorAll('.review-card').length===1 && document.querySelector('#review-form-wrapper').hidden"
                )
                with factory() as db:
                    review = db.scalar(select(Review).where(Review.booking_id == completed_id))
                    check(
                        review is not None and review.rating == 5,
                        "customer browser posts exactly one eligible booking review",
                    )
                check(
                    c.js(
                        "!globalThis.reviewXss && !document.querySelector('.review-card img') && document.querySelector('.review-card__name').textContent!=='Spoofed Author'"
                    ),
                    "review is safe text and author comes from authenticated account",
                )
                c.call("Page.reload")
                c.until("document.querySelectorAll('.review-card').length===1")
                check(
                    c.js("document.querySelector('#detail-rating').textContent==='5.0'"),
                    "public rating reload is calculated from persisted review",
                )
                simulation_payload = {
                    **payload,
                    "checkIn": (today + timedelta(days=30)).isoformat(),
                    "checkOut": (today + timedelta(days=31)).isoformat(),
                }
                simulation_booking = client.post(
                    "/api/me/bookings",
                    json=simulation_payload,
                    headers={**user_header, "Idempotency-Key": secrets.token_urlsafe(24)},
                )
                assert simulation_booking.status_code == 201
                simulation_id = simulation_booking.json()["id"]
                simulation_header = {"Authorization": "Bearer " + admin["access_token"]}
                simulation_path = f"/api/admin/bookings/{simulation_id}/payment-simulation"
                assert (
                    client.post(
                        simulation_path,
                        json={"action": "paid", "reason": "Explicit disposable browser test simulation"},
                        headers=simulation_header,
                    ).status_code
                    == 200
                )
                page(
                    f"booking-detail.html?mode=api&id={simulation_id}",
                    "document.querySelector('#booking-payment-state')?.textContent.includes('M\u00f4 ph\u1ecfng')",
                )
                check(
                    c.js(
                        "document.querySelector('#booking-payment-state').textContent.includes('kh\u00f4ng x\u00e1c nh\u1eadn ng\u00e2n h\u00e0ng')"
                    ),
                    "simulated paid is explicitly not bank confirmation",
                )
                c.js("document.querySelector('#bd-cancel').click()")
                c.until("document.querySelector('#confirm-dialog').open")
                c.js("document.querySelector('#confirm-dialog [data-confirm]').click()")
                c.until(
                    "document.querySelector('#booking-payment-state')?.textContent.includes('\u0110ang ch\u1edd ho\u00e0n ti\u1ec1n')"
                )
                check(True, "customer cancellation displays simulated refund_pending from DB")
                assert (
                    client.post(
                        simulation_path,
                        json={"action": "refunded", "reason": "Explicit disposable test refund"},
                        headers=simulation_header,
                    ).status_code
                    == 200
                )
                c.call("Page.reload")
                c.until(
                    "document.querySelector('#booking-payment-state')?.textContent.includes('\u0110\u00e3 ghi nh\u1eadn ho\u00e0n ti\u1ec1n')"
                )
                check(
                    c.js(
                        "document.querySelector('#booking-payment-state').textContent.startsWith('M\u00f4 ph\u1ecfng')"
                    ),
                    "refunded remains explicitly simulated after reload",
                )
                applicant_email = "reject-" + secrets.token_hex(5) + "@example.com"
                application_response = client.post(
                    "/api/auth/register",
                    json={
                        "email": applicant_email,
                        "password": password,
                        "display_name": "<svg onload=globalThis.adminXss=1>",
                        "role": "host",
                        "phone": "0912345678",
                    },
                )
                assert application_response.status_code == 201
                with factory() as db:
                    pending_owner = db.scalar(select(User).where(User.email == host_email))
                    owner_id = pending_owner.id
                    approve_app = db.scalar(
                        select(HostApplication).where(HostApplication.user_id == owner_id)
                    )
                    approve_id = approve_app.id
                    reject_owner = db.scalar(select(User).where(User.email == applicant_email))
                    reject_app = db.scalar(
                        select(HostApplication).where(HostApplication.user_id == reject_owner.id)
                    )
                    reject_app_id = reject_app.id
                login(admin_email, password)
                page(
                    "admin.html?mode=api",
                    "!!document.querySelector('[data-application-id]') && !!document.querySelector('#admin-users [data-user-id]') && !!document.querySelector('#admin-homestays [data-homestay-id]') && document.querySelector('#period-note').textContent.includes('kh\u00f4ng ph\u1ea3i giao d\u1ecbch')",
                )
                check(
                    c.js("!globalThis.adminXss && !document.querySelector('#application-list svg')"),
                    "admin applications render hostile display names as text",
                )
                c.js(
                    "document.querySelector('[data-application-id=\""
                    + str(approve_id)
                    + "\"] [data-action=approve]').click()"
                )
                c.until("document.querySelector('#confirm-dialog').open")
                c.js("document.querySelector('#confirm-dialog [data-confirm]').click()")
                c.until("!document.querySelector('[data-application-id=\"" + str(approve_id) + "\"]')")
                with factory() as db:
                    check(
                        db.get(User, owner_id).role == "host"
                        and db.get(HostApplication, approve_id).status == "approved",
                        "admin UI approval persists and grants host through backend policy",
                    )
                c.js(
                    "document.querySelector('[data-application-id=\""
                    + str(reject_app_id)
                    + "\"] [data-action=reject]').click()"
                )
                c.until("document.querySelector('#reject-dialog').open")
                c.js(
                    "document.querySelector('#rejectReason').value='Incomplete application';document.querySelector('#rejectConfirm').click()"
                )
                c.until(
                    "!document.querySelector('#reject-dialog').open && !document.querySelector('[data-application-id=\""
                    + str(reject_app_id)
                    + "\"]')"
                )
                with factory() as db:
                    check(
                        db.get(HostApplication, reject_app_id).status == "rejected",
                        "admin UI rejection persists reason and leaves customer role",
                    )
                c.js(
                    "document.querySelector('[data-user-id=\""
                    + str(owner_id)
                    + "\"] [data-action=toggle-active]').click()"
                )
                c.until("document.querySelector('#confirm-dialog').open")
                c.js("document.querySelector('#confirm-dialog [data-confirm]').click()")
                c.until(
                    "document.querySelector('[data-user-id=\""
                    + str(owner_id)
                    + "\"] [data-action=toggle-active]').textContent==='M\u1edf kh\u00f3a'"
                )
                with factory() as db:
                    check(not db.get(User, owner_id).is_active, "admin UI locks actual account")
                check(
                    client.get("/api/me/profile", headers=user_header).status_code == 401,
                    "locked account cannot reuse old bearer session",
                )
                c.js(
                    "document.querySelector('[data-user-id=\""
                    + str(owner_id)
                    + "\"] [data-action=toggle-active]').click()"
                )
                c.until("document.querySelector('#confirm-dialog').open")
                c.js("document.querySelector('#confirm-dialog [data-confirm]').click()")
                c.until(
                    "document.querySelector('[data-user-id=\""
                    + str(owner_id)
                    + "\"] [data-action=toggle-active]').textContent==='Kh\u00f3a'"
                )
                c.js(
                    "document.querySelector('[data-homestay-id=\""
                    + str(sid)
                    + "\"] input').value='Policy review';document.querySelector('[data-homestay-id=\""
                    + str(sid)
                    + "\"] [data-action=moderate]').click()"
                )
                c.until("document.querySelector('#confirm-dialog').open")
                c.js("document.querySelector('#confirm-dialog [data-confirm]').click()")
                c.until(
                    "document.querySelector('[data-homestay-id=\""
                    + str(sid)
                    + "\"] [data-action=moderate]').textContent==='K\u00edch ho\u1ea1t'"
                )
                check(
                    client.get(f"/api/items/{sid}").status_code == 404,
                    "admin moderation immediately removes property from public catalog",
                )
                for width in [1440, 1024, 768, 375]:
                    c.call(
                        "Emulation.setDeviceMetricsOverride",
                        width=width,
                        height=950,
                        deviceScaleFactor=1,
                        mobile=width == 375,
                    )
                    check(
                        c.js("document.documentElement.scrollWidth<=innerWidth"),
                        "admin API layout without horizontal overflow " + str(width),
                    )
                    screenshot = c.call("Page.captureScreenshot", format="png", captureBeyondViewport=False)
                    (parent / f"phase9-admin-{width}.png").write_bytes(base64.b64decode(screenshot["data"]))
                c.call("Page.reload")
                c.until(
                    "document.querySelector('[data-homestay-id=\""
                    + str(sid)
                    + "\"] [data-action=moderate]')?.textContent==='K\u00edch ho\u1ea1t'"
                )
                check(True, "admin reload reads persisted moderation state")
                with factory() as db:
                    property_host_id = db.scalar(select(User.id).where(User.email == email))
                host_lock_selector = (
                    '[data-user-id="' + str(property_host_id) + '"] [data-action=toggle-active]'
                )
                c.js("document.querySelector(" + json.dumps(host_lock_selector) + ").click()")
                c.until("document.querySelector('#confirm-dialog').open")
                c.js("document.querySelector('#confirm-dialog [data-confirm]').click()")
                c.until(
                    "document.querySelector("
                    + json.dumps(host_lock_selector)
                    + ').textContent==="M\u1edf kh\u00f3a"'
                )
                check(
                    client.get(f"/api/items/{other_stay['id']}").status_code == 404,
                    "admin UI lock of property owner removes public catalog entry",
                )
                check(
                    client.get("/api/host/homestays", headers=host_header).status_code == 401,
                    "locked property owner old JWT is revoked",
                )
                c.js("document.querySelector(" + json.dumps(host_lock_selector) + ").click()")
                c.until("document.querySelector('#confirm-dialog').open")
                c.js("document.querySelector('#confirm-dialog [data-confirm]').click()")
                c.until(
                    "document.querySelector(" + json.dumps(host_lock_selector) + ').textContent==="Kh\u00f3a"'
                )
                check(
                    client.get(f"/api/items/{other_stay['id']}").status_code == 200,
                    "unlock restores active catalog while old sessions remain revoked",
                )
                check(not c.errors, "no uncaught JavaScript errors in customer API flow")
                report = {
                    "status": "PASS",
                    "checks": checks,
                    "count": len(checks),
                    "viewports": [1440, 1024, 768, 375],
                    "backend": "FastAPI/Uvicorn, separate migrated SQLite",
                    "frontend": "real Chrome/Edge over separate HTTP origin",
                    "playwright": False,
                    "scope": "accounts/customer checkout, host property/room/blocks/bookings/dashboard, admin approval/users/moderation browser UI on shared SQLite; initial fixtures via API harness",
                }
                (parent / "phase8-accounts-report.json").write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(json.dumps(report, ensure_ascii=True))
            finally:
                if chrome:
                    chrome.terminate()
                    chrome.wait(timeout=20)
                server.terminate()
                server.wait(timeout=20)
                front.shutdown()
                front.server_close()
                engine.dispose()


if __name__ == "__main__":
    main()
