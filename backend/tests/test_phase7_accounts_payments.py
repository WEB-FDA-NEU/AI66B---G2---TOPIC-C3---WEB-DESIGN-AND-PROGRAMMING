"""Phase 7 security, payment states, profile and review acceptance."""

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from backend.main import create_app
from backend.models import Booking, Payment, PaymentEvent, Review, RoomNight


def new_booking(client, headers, body):
    response = client.post("/api/me/bookings", json=body, headers=headers())
    assert response.status_code == 201
    return response.json()


def sim(client, headers, bid, action="paid", uid=5, **fields):
    return client.post(
        f"/api/admin/bookings/{bid}/payment-simulation",
        json={"action": action, "reason": "Explicit test simulation", **fields},
        headers=headers(uid) if uid else {},
    )


def test_payment_simulation_paid_refund_audit_and_replay(client, headers, booking_payload, setup):
    b = new_booking(client, headers, booking_payload)
    p = client.get(f"/api/me/bookings/{b['id']}/payments", headers=headers()).json()[0]
    assert p["status"] == "pending" and len(p["history"]) == 1
    paid = sim(client, headers, b["id"])
    assert paid.status_code == 200 and paid.json()["simulated"] is True
    assert paid.json()["amount"] == b["totalPrice"]
    metrics = client.get("/api/host/dashboard", headers=headers(3)).json()["payments"]
    assert metrics["paidRevenue"] == 0 and metrics["grossCaptured"] == 0
    assert metrics["simulatedCaptured"] == b["totalPrice"]
    assert sim(client, headers, b["id"]).json() == paid.json()
    assert client.get(f"/api/me/bookings/{b['id']}/payments", headers=headers(2)).status_code == 404
    assert client.post(f"/api/me/bookings/{b['id']}/cancel", headers=headers()).status_code == 200
    pending = client.get(f"/api/me/bookings/{b['id']}/payments", headers=headers()).json()[0]
    assert pending["status"] == "refund_pending"
    refund = sim(client, headers, b["id"], "refunded")
    assert refund.status_code == 200 and refund.json()["status"] == "refunded"
    assert refund.json()["history"][-1]["refundAmount"] == b["totalPrice"]
    assert sim(client, headers, b["id"], "refunded").json() == refund.json()
    metrics = client.get("/api/admin/overview", headers=headers(5)).json()["kpis"]["payments"]
    assert metrics["paidRevenue"] == 0 and metrics["refunded"] == 0
    assert metrics["simulatedRefunded"] == b["totalPrice"] and metrics["simulatedNet"] == 0
    assert sim(client, headers, b["id"], "paid").status_code == 409
    with setup["factory"]() as db:
        assert db.scalar(select(func.count()).select_from(Payment)) == 1
        assert db.scalar(select(func.count()).select_from(PaymentEvent)) == 4
        assert db.scalar(select(func.count()).select_from(RoomNight)) == 0


@pytest.mark.parametrize("uid,status", [(None, 401), (1, 403), (3, 403)])
def test_payment_simulation_not_public_or_customer_host(client, headers, booking_payload, uid, status):
    b = new_booking(client, headers, booking_payload)
    assert sim(client, headers, b["id"], uid=uid).status_code == status


def test_production_rejects_simulation_without_state_change(setup, client, headers, booking_payload):
    b = new_booking(client, headers, booking_payload)
    settings = replace(
        setup["settings"],
        environment="production",
        database_url="postgresql+psycopg://unused/production_test",
    )
    # Dependency injection retains the isolated test engine, never connects to a production DB.
    with TestClient(create_app(settings, setup["engine"])) as prod:
        assert sim(prod, headers, b["id"]).status_code == 403
    assert (
        client.get(f"/api/me/bookings/{b['id']}/payments", headers=headers()).json()[0]["status"] == "pending"
    )


@pytest.mark.parametrize("fields", [{"amount": 1}, {"status": "paid"}, {"cvv": "123"}, {"action": "failed"}])
def test_payment_forgery_fields_rejected(client, headers, booking_payload, fields):
    b = new_booking(client, headers, booking_payload)
    assert sim(client, headers, b["id"], **fields).status_code == 422


def test_payment_inconsistent_amount_and_refund_reject_atomically(setup, client, headers, booking_payload):
    b = new_booking(client, headers, booking_payload)
    with setup["factory"]() as db:
        payment = db.scalar(select(Payment))
        payment.amount = 1
        db.commit()
    assert sim(client, headers, b["id"]).status_code == 409
    assert client.post(f"/api/me/bookings/{b['id']}/cancel", headers=headers()).status_code == 409
    with setup["factory"]() as db:
        assert db.get(Booking, b["id"]).status == "pending"
        assert db.scalar(select(func.count()).select_from(RoomNight)) == 2
        db.scalar(select(Payment)).amount = b["totalPrice"]
        db.commit()
    assert sim(client, headers, b["id"], "refunded").status_code == 409
    assert sim(client, headers, b["id"]).status_code == 200
    assert client.post(f"/api/me/bookings/{b['id']}/cancel", headers=headers()).status_code == 200
    with setup["factory"]() as db:
        db.get(Booking, b["id"]).refund_due = b["totalPrice"] + 1
        db.commit()
    assert sim(client, headers, b["id"], "refunded").status_code == 409
    assert (
        client.get(f"/api/me/bookings/{b['id']}/payments", headers=headers()).json()[0]["status"]
        == "refund_pending"
    )


@pytest.mark.parametrize("action", ["paid", "refunded"])
def test_parallel_payment_or_refund_not_duplicated(setup, client, headers, booking_payload, action):
    b = new_booking(client, headers, booking_payload)
    if action == "refunded":
        assert sim(client, headers, b["id"]).status_code == 200
        assert client.post(f"/api/me/bookings/{b['id']}/cancel", headers=headers()).status_code == 200
    barrier = Barrier(2)

    def pay(_):
        barrier.wait(timeout=10)
        return sim(client, headers, b["id"], action).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(pay, range(2))) == [200, 200]
    with setup["factory"]() as db:
        assert (
            db.scalar(select(func.count()).select_from(PaymentEvent).where(PaymentEvent.new_status == action))
            == 1
        )


def test_payment_event_failure_rolls_back_payment(setup, client, headers, booking_payload):
    from sqlalchemy.orm import Session

    b = new_booking(client, headers, booking_payload)

    def fail(session, *_):
        for row in session.new:
            if isinstance(row, PaymentEvent) and row.new_status == "paid":
                row.refund_amount = row.amount + 1

    event.listen(Session, "before_flush", fail)
    try:
        assert sim(client, headers, b["id"]).status_code == 409
    finally:
        event.remove(Session, "before_flush", fail)
    response = client.get(f"/api/me/bookings/{b['id']}/payments", headers=headers()).json()[0]
    assert response["status"] == "pending" and response["transactionReference"] is None
    assert len(response["history"]) == 1


def test_partial_profile_update_and_duplicate_email(client, headers):
    before = client.get("/api/me/profile", headers=headers()).json()
    response = client.patch("/api/me/profile", json={"display_name": "Partial Updated"}, headers=headers())
    assert response.status_code == 200 and response.json()["email"] == before["email"]
    assert (
        client.patch("/api/me/profile", json={"email": "account2@example.com"}, headers=headers()).status_code
        == 409
    )
    assert client.get("/api/me/profile", headers=headers()).json()["email"] == before["email"]


@pytest.mark.parametrize(
    "fields",
    [
        {"role": "admin"},
        {"is_active": True},
        {"password_hash": "fake"},
        {"token_version": 0},
        {"id": 2},
        {"phone": None},
        {"avatar": "https://["},
    ],
)
def test_patch_profile_rejects_privileged_or_invalid_fields(client, headers, fields):
    before = client.get("/api/me/profile", headers=headers()).json()
    response = client.patch("/api/me/profile", json=fields, headers=headers())
    assert response.status_code == 422
    assert client.get("/api/me/profile", headers=headers()).json() == before


@pytest.mark.parametrize(
    "path,method,body",
    [
        ("/api/me/profile", "PATCH", {"display_name": "\ud800\ud800"}),
        ("/api/me/profile", "PUT", {"display_name": "\ud800\ud800", "email": "test@example.com"}),
        ("/api/items/1/reviews", "POST", {"rating": 5, "comment": "\ud800" * 5}),
    ],
)
def test_phase7_invalid_unicode_returns_redacted_422(client, headers, path, method, body):
    result = client.request(
        method,
        path,
        content=json.dumps(body, ensure_ascii=True),
        headers={**headers(), "Content-Type": "application/json"},
    )
    assert result.status_code == 422 and "ud800" not in result.text


def completed(client, headers, payload, setup, uid=1):
    response = client.post("/api/me/bookings", json=payload, headers=headers(uid))
    assert response.status_code == 201
    b = response.json()
    with setup["factory"]() as db:
        db.get(Booking, b["id"]).status = "completed"
        db.commit()
    return b


def test_review_rules_pagination_true_average_and_untrusted_text(setup, client, headers, booking_payload):
    b = completed(client, headers, booking_payload, setup)
    body = {"bookingId": b["id"], "rating": 5, "comment": "<img src=x onerror=alert(1)> untrusted text"}
    assert client.post("/api/items/1/reviews", json=body, headers=headers(2)).status_code == 409
    assert client.post("/api/items/2/reviews", json=body, headers=headers()).status_code == 409
    assert client.post("/api/items/1/reviews", json=body, headers=headers()).status_code == 201
    assert client.post("/api/items/1/reviews", json=body, headers=headers()).status_code == 409
    other = completed(client, headers, booking_payload, setup, uid=2)
    assert (
        client.post(
            "/api/items/1/reviews",
            json={"bookingId": other["id"], "rating": 3, "comment": "Another valid review"},
            headers=headers(2),
        ).status_code
        == 201
    )
    assert client.get("/api/items/1").json()["rating"] == 4
    first = client.get("/api/items/1/reviews", params={"page_size": 1}).json()
    second = client.get("/api/items/1/reviews", params={"page_size": 1, "page": 2}).json()
    assert len(first) == len(second) == 1 and first[0]["id"] != second[0]["id"]
    assert "<img" in second[0]["comment"]  # Stored as untrusted plain text; integration must escape.
    assert client.get("/api/items/1/reviews", params={"page": 0}).status_code == 422
    assert (
        client.post(
            "/api/items/1/reviews", json={"rating": 6, "comment": "Invalid rating"}, headers=headers()
        ).status_code
        == 422
    )


def test_review_pending_cancelled_and_role_bypass_rejected(client, headers, booking_payload):
    b = new_booking(client, headers, booking_payload)
    body = {"bookingId": b["id"], "rating": 5, "comment": "Not eligible yet"}
    assert client.post("/api/items/1/reviews", json=body, headers=headers()).status_code == 409
    assert client.post(f"/api/me/bookings/{b['id']}/cancel", headers=headers()).status_code == 200
    assert client.post("/api/items/1/reviews", json=body, headers=headers()).status_code == 409
    assert client.post("/api/items/1/reviews", json=body, headers=headers(3)).status_code == 403
    assert client.post("/api/items/1/reviews", json=body).status_code == 401


def test_concurrent_reviews_only_one_persists(setup, client, headers, booking_payload):
    b = completed(client, headers, booking_payload, setup)
    barrier = Barrier(2)

    def review(_):
        barrier.wait(timeout=10)
        return client.post(
            "/api/items/1/reviews",
            json={"bookingId": b["id"], "rating": 5, "comment": "Concurrent review"},
            headers=headers(),
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(review, range(2))) == [201, 409]
    with setup["factory"]() as db:
        assert db.scalar(select(func.count()).select_from(Review)) == 1


def test_payment_event_migration_keeps_legacy_payment_and_ledger(empty_engine):
    from datetime import date

    from backend.database import make_session_factory
    from backend.models import BookingLine, Homestay, Room, User

    from .conftest import migrate

    migrate(empty_engine, "0004_app_history")
    factory = make_session_factory(empty_engine)
    with factory() as db:
        user = User(email="legacy.payment@example.com", display_name="Legacy", password_hash="not-real")
        db.add(user)
        db.flush()
        stay = Homestay(
            host_id=user.id, name="Legacy Stay", address="Da Lat", city="Da Lat", location="Da Lat"
        )
        db.add(stay)
        db.flush()
        room = Room(
            homestay_id=stay.id, key="legacy", name="Room", price_per_night=100, capacity=2, inventory=1
        )
        db.add(room)
        db.flush()
        b = Booking(
            code="BK-LEGACY",
            customer_id=user.id,
            homestay_id=stay.id,
            check_in=date(2099, 1, 1),
            check_out=date(2099, 1, 2),
            adults=1,
            guest_name="Legacy",
            guest_email=user.email,
            room_subtotal=100,
            service_fee=5,
            total_price=105,
            homestay_name=stay.name,
            homestay_image="img/placeholder.svg",
            host_address=stay.address,
            host_phone="",
        )
        db.add(b)
        db.flush()
        payment = Payment(
            booking_id=b.id, amount=105, status="paid", transaction_reference="LEGACY-REFERENCE"
        )
        db.add(payment)
        db.add(
            BookingLine(
                booking_id=b.id,
                room_id=room.id,
                room_name=room.name,
                room_key=room.key,
                quantity=1,
                capacity=2,
                price_per_night=100,
            )
        )
        db.add(RoomNight(booking_id=b.id, room_id=room.id, unit=1, night=date(2099, 1, 1)))
        db.commit()
        pid = payment.id
    migrate(empty_engine)
    with factory() as db:
        entry = db.scalar(select(PaymentEvent))
        assert entry.payment_id == pid and entry.source == "legacy_snapshot" and entry.new_status == "paid"
        assert entry.amount == 105 and entry.refund_amount == 0
        assert db.get(Payment, pid).transaction_reference == "LEGACY-REFERENCE"
        assert db.scalar(select(func.count()).select_from(RoomNight)) == 1
        assert db.scalar(select(func.count()).select_from(BookingLine)) == 1
