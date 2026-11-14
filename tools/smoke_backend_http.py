"""Real HTTP smoke test in a private temporary SQLite database (no frontend integration)."""

import os
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import httpx

    from backend.database import make_engine, make_session_factory
    from backend.seed import seed_database
    from backend.tests.conftest import migrate

    parent = (ROOT / "backend/.test-tmp").resolve()
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="http-", dir=parent, ignore_cleanup_errors=True) as temporary:
        work = Path(temporary).resolve()
        if work.parent != parent:
            raise RuntimeError("Unsafe temporary path")
        database_url = "sqlite:///" + (work / "smoke.db").as_posix()
        password = secrets.token_urlsafe(24)
        engine = make_engine(database_url)
        try:
            migrate(engine)
            with make_session_factory(engine)() as db:
                seed_database(db, password, "test")
        finally:
            engine.dispose()
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        environment = os.environ.copy()
        environment.update(
            APP_ENV="test",
            DATABASE_URL=database_url,
            JWT_SECRET=secrets.token_urlsafe(48),
            UPLOAD_DIR=str(work / "uploads"),
            SERVE_FRONTEND="true",
        )
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        with (work / "server.log").open("w") as log:
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
            try:
                with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=15) as client:
                    for _ in range(100):
                        try:
                            if client.get("/api/ready").status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        time.sleep(0.1)
                    else:
                        raise RuntimeError("HTTP server was not ready")
                    assert client.get("/index.html").status_code == 200
                    assert "USE_MOCK = true" in client.get("/js/config.js").text
                    catalog = client.get("/api/items").json()
                    assert catalog["total"] > 0 and all(
                        item["status"] == "active" for item in catalog["items"]
                    )
                    registration = client.post(
                        "/api/auth/register",
                        json={
                            "display_name": "HTTP Customer",
                            "email": "http.customer@example.com",
                            "password": password,
                        },
                    )
                    assert registration.status_code == 201
                    customer = {"Authorization": "Bearer " + registration.json()["access_token"]}
                    host = client.post(
                        "/api/auth/login", json={"email": "host@test.com", "password": password}
                    )
                    assert host.status_code == 200
                    host_header = {"Authorization": "Bearer " + host.json()["access_token"]}
                    from datetime import timedelta

                    from backend.booking_service import business_today

                    stay = business_today() + timedelta(days=60)
                    item = client.get("/api/items/1").json()
                    room = item["roomTypes"][0]
                    payload = {
                        "homestayId": 1,
                        "checkIn": stay.isoformat(),
                        "checkOut": (stay + timedelta(days=2)).isoformat(),
                        "adults": 1,
                        "rooms": [{"key": room["key"], "qty": 1}],
                        "guestName": "HTTP Guest",
                        "guestEmail": "http.guest@example.com",
                    }
                    quote = client.post("/api/bookings/quote", json=payload)
                    assert quote.status_code == 200
                    booking = client.post(
                        "/api/me/bookings",
                        json={**payload, "totalPrice": 1},
                        headers={**customer, "Idempotency-Key": "http-smoke"},
                    )
                    assert (
                        booking.status_code == 201 and booking.json()["totalPrice"] == quote.json()["total"]
                    )
                    bid = booking.json()["id"]
                    assert client.get("/api/host/bookings", headers=host_header).json()[0]["bookingId"] == bid
                    assert (
                        client.patch(
                            f"/api/host/bookings/{bid}/status",
                            json={"status": "confirmed"},
                            headers=host_header,
                        ).status_code
                        == 200
                    )
                    assert client.post(f"/api/me/bookings/{bid}/cancel", headers=customer).status_code == 200
                    assert client.post("/api/auth/logout", headers=customer).status_code == 204
                    assert client.get("/api/me", headers=customer).status_code == 401
                    assert client.get("/api/admin/overview", headers=host_header).status_code == 403
                    print(
                        "HTTP smoke passed: real Uvicorn, migrated DB, catalog, quote, booking, host confirmation, cancellation, logout, ownership; frontend still mock"
                    )
            finally:
                if os.name == "nt":
                    # Windows venv launchers may spawn a child interpreter; terminate only this test tree.
                    subprocess.run(
                        ["taskkill", "/PID", str(server.pid), "/T", "/F"],
                        capture_output=True,
                        creationflags=flags,
                    )
                else:
                    server.terminate()
                server.wait(timeout=15)


if __name__ == "__main__":
    main()
