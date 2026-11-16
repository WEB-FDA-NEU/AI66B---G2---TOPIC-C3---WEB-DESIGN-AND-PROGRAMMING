"""Booking history regression through real mock checkout in an isolated Chrome profile."""

import functools
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ui", ROOT / "tests/ui-browser.py")
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


def main():
    browser = (
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe"
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(ui.Handler, directory=str(ROOT)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = (
        sys.argv[1].rstrip("/") if len(sys.argv) > 1 else f"http://127.0.0.1:{server.server_port}/frontend"
    )
    checks = []
    with tempfile.TemporaryDirectory(prefix="history-browser-", ignore_cleanup_errors=True) as profile:
        chrome = subprocess.Popen(
            [
                str(browser),
                "--headless=new",
                "--disable-gpu",
                "--no-first-run",
                "--remote-debugging-port=0",
                "--user-data-dir=" + profile,
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            active = Path(profile) / "DevToolsActivePort"
            for _ in range(150):
                if active.exists():
                    break
                time.sleep(0.1)
            port = active.read_text().splitlines()[0]
            targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json"))
            c = ui.CDP(next(t["webSocketDebuggerUrl"] for t in targets if t["type"] == "page"))
            c.call("Page.enable")
            c.call("Runtime.enable")

            def navigate(route, ready):
                c.call("Page.navigate", url=origin + "/" + route)
                c.until("document.readyState==='complete' && (" + ready + ")")

            def check(condition, label):
                assert condition, label
                checks.append(label)

            navigate("login.html", "document.querySelector('#login-form [type=submit]')?.disabled===false")
            check(
                c.js("import('./js/config.js').then(config=>!config.ACCOUNT_API_MODE)"),
                "test origin uses isolated mock data only",
            )
            c.js(
                "import('./js/api.js').then(async api=>(await import('./js/auth.js')).saveSession(await api.login('huy@test.com','12345678')))"
            )
            # Use the actual detail room selection and checkout form.
            navigate("detail.html?id=3", "!!document.querySelector('.room-pick:not(:disabled)')")
            c.js("document.querySelector('.room-pick:not(:disabled)').click()")
            c.until("document.querySelector('#book-btn')?.disabled===false")
            c.js("document.querySelector('#book-btn').click()")
            c.until(
                "location.pathname.endsWith('/booking-page.html') && document.querySelector('#btnSubmit')?.disabled===false"
            )
            c.js("document.querySelector('#checkoutForm').requestSubmit()")
            c.until(
                "location.pathname.endsWith('/booking-confirmed.html') && document.querySelector('#bCode')?.textContent.startsWith('BK')"
            )
            check(True, "real mock checkout reaches confirmation")
            code = c.js("document.querySelector('#bCode').textContent")
            c.js("document.querySelector('a[href*=\"booking-list.html\"]').click()")
            c.until(
                "location.pathname.endsWith('/booking-list.html') && !!document.querySelector('#booking-list .row')"
            )
            visible = "(()=>{const row=document.querySelector('#booking-list .row');return !!row && !document.querySelector('#booking-list').hidden && getComputedStyle(row).visibility==='visible' && row.getBoundingClientRect().height>0})()"
            check(c.js(visible), "customer sees visible booking history after checkout")
            c.call("Page.reload")
            c.until("!!document.querySelector('#booking-list .row')")
            check(c.js(visible), "history stays visible after reload")
            # A version bump must preserve actual low-ID customer bookings.
            c.js("localStorage.setItem('mock_version','older-release')")
            c.call("Page.reload")
            c.until("document.body.hasAttribute('data-guard-ok')")
            check(
                c.js(
                    "JSON.parse(localStorage.getItem('customerBookings')).some(row=>row.code==="
                    + json.dumps(code)
                    + ")"
                ),
                "mock migration preserves the real first booking of demo customer",
            )
            c.until("!!document.querySelector('#booking-list .row')")
            check(c.js(visible), "history remains visible after mock migration")
            # Support the wrapped shape retained by older versions, without resetting records.
            c.js(
                "localStorage.setItem('customerBookings',JSON.stringify({customerBookings:JSON.parse(localStorage.getItem('customerBookings'))}))"
            )
            c.call("Page.reload")
            c.until("!!document.querySelector('#booking-list .row')")
            check(c.js(visible), "legacy wrapped cache is read without losing booking history")
            c.js(
                "localStorage.setItem('customerBookings',JSON.stringify({bookings:JSON.parse(localStorage.getItem('customerBookings'))}))"
            )
            c.call("Page.reload")
            c.until("!!document.querySelector('#booking-list .row')")
            check(c.js(visible), "older bookings wrapper preserves owned history")
            c.js("document.querySelector('[data-filter=pending]').click()")
            check(
                c.js(
                    "!document.querySelector('#booking-empty').hidden && document.querySelector('#booking-empty .empty__action').textContent.includes('Xem')"
                ),
                "empty status tab offers return to all bookings",
            )
            c.js("document.querySelector('#booking-empty .empty__action').click()")
            check(c.js(visible), "all bookings action restores confirmed history")
            data = c.js(
                "(async()=>{const api=await import('./js/api.js');const pricing=await import('./js/pricing.js');const item=await api.getItem(3);const start=pricing.toISO(pricing.addDays(new Date(),30));const end=pricing.toISO(pricing.addDays(new Date(),32));const q=pricing.quote({item,rooms:{superior:1},checkin:start,checkout:end});const payload={homestayId:3,homestayName:item.title,homestayImage:item.cover_url,checkIn:start,checkOut:end,adults:2,children:0,guests:2,rooms:q.lines.map(l=>({key:l.key,qty:l.qty})),roomName:q.lines[0].name,nights:q.nights,totalPrice:q.total,guestName:'Test Guest',guestEmail:'huy@test.com'};await api.reserveBookingHold(payload);const created=await api.createBooking({...payload,id:'forged',userId:'other-user',status:'cancelled'});return{id:created.id,owner:created.userId,status:created.status}})()"
            )
            check(
                data["owner"] == 1 and data["id"] != "forged" and data["status"] == "confirmed",
                "booking keeps authenticated owner and generated identity",
            )
            denied = c.js(
                "(async()=>{const api=await import('./js/api.js');const auth=await import('./js/auth.js');auth.saveSession(await api.register({display_name:'Other Customer',email:'other-history@example.com',password:'Test-History-123!'}));try{await api.cancelBooking("
                + json.dumps(data["id"])
                + ");return 200}catch(error){return error.status}})()"
            )
            check(denied == 404, "another customer cannot cancel the booking")
            check(
                c.js("import('./js/api.js').then(async api=>(await api.getBookings()).length===0)"),
                "another customer does not see private booking history",
            )
            c.js(
                "import('./js/api.js').then(async api=>(await import('./js/auth.js')).saveSession(await api.login('huy@test.com','12345678')))"
            )
            c.call("Page.reload")
            c.until("document.querySelectorAll('#booking-list .row').length===2")
            check(c.js(visible), "logout and login again preserves both owned bookings")
            cache = c.js("localStorage.getItem('customerBookings')")
            c.js("localStorage.setItem('customerBookings','{broken')")
            c.call("Page.reload")
            c.until("!!document.querySelector('#booking-list .empty__action')")
            check(
                c.js(
                    "localStorage.getItem('customerBookings')==='{broken' && !document.querySelector('#booking-list').hidden"
                ),
                "invalid cache shows an error without resetting stored data",
            )
            c.js(
                "localStorage.setItem('customerBookings',"
                + json.dumps(cache)
                + ");document.querySelector('#booking-list .empty__action').click()"
            )
            c.until("document.querySelectorAll('#booking-list .row').length===2")
            check(c.js(visible), "retry reloads restored booking history")
            c.js(
                "const oldRows=JSON.parse(localStorage.getItem('customerBookings'));localStorage.setItem('bookings',JSON.stringify([oldRows[0]]));localStorage.setItem('customerBookings','[]')"
            )
            c.call("Page.reload")
            c.until(
                "document.body.hasAttribute('data-guard-ok') && !document.querySelector('#booking-list .skeleton-card')"
            )
            check(c.js(visible), "customer sees owned legacy booking stored under bookings key")
            legacy_id = c.js("import('./js/api.js').then(async api=>(await api.getBookings())[0].id)")
            check(
                c.js(
                    "import('./js/api.js').then(async api=>(await api.getBooking("
                    + json.dumps(legacy_id)
                    + ")).userId===1)"
                ),
                "legacy history opens its own booking detail",
            )
            c.js("import('./js/api.js').then(api=>api.cancelBooking(" + json.dumps(legacy_id) + "))")
            check(
                c.js("JSON.parse(localStorage.getItem('bookings'))[0].status==='cancelled'"),
                "legacy cancellation updates original booking record",
            )
            c.js("localStorage.setItem('customerBookings',localStorage.getItem('bookings'))")
            check(
                c.js("import('./js/api.js').then(async api=>(await api.getBookings()).length===1)"),
                "same booking in both old stores is shown only once",
            )
            c.js(
                "localStorage.setItem('bookings',JSON.stringify([{...JSON.parse(localStorage.getItem('bookings'))[0],userId:'someone-else',code:'PRIVATE-OTHER'}]));localStorage.setItem('customerBookings','[]')"
            )
            check(
                c.js("import('./js/api.js').then(async api=>(await api.getBookings()).length===0)"),
                "legacy records of another user are excluded",
            )
            check(not c.errors, "no uncaught browser errors")
            print(json.dumps({"status": "PASS", "count": len(checks), "checks": checks}))
        finally:
            chrome.terminate()
            chrome.wait(timeout=20)
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
