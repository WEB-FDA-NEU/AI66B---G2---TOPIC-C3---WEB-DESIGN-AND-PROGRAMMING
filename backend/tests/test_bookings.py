from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier

import pytest
from sqlalchemy import func, select

from backend.models import Booking, BookingLine, Payment, Room, RoomNight


def test_quote_ignores_client_prices_and_snapshots(client, booking_payload):
    response = client.post(
        "/api/bookings/quote", json={**booking_payload, "totalPrice": 1, "pricePerNight": 1}
    )
    assert response.status_code == 200
    quote = response.json()
    assert (quote["roomSubtotal"], quote["serviceFee"], quote["total"]) == (200000, 10000, 210000)


def test_booking_is_one_canonical_order_visible_to_customer_and_host(client, headers, booking_payload):
    booking_payload.update(
        totalPrice=1, homestayName="Forged Name", hostPhone="Fake", userId=2, status="completed"
    )
    response = client.post("/api/me/bookings", json=booking_payload, headers=headers())
    assert response.status_code == 201
    booking = response.json()
    assert booking["totalPrice"] == 210000 and booking["userId"] == 1 and booking["status"] == "pending"
    assert booking["homestayName"] == "Homestay 1" and booking["hostPhone"] == "0912345678"
    host = client.get("/api/host/bookings", headers=headers(3)).json()
    assert len(host) == 1 and host[0]["bookingId"] == booking["id"]
    assert client.get("/api/me/bookings", headers=headers(2)).json() == []
    assert client.get(f"/api/me/bookings/{booking['id']}", headers=headers(2)).status_code == 404
    assert (
        client.patch(
            f"/api/host/bookings/{booking['id']}/status", json={"status": "confirmed"}, headers=headers(4)
        ).status_code
        == 404
    )


def test_multi_room_booking_snapshots_and_total(client, headers, booking_payload, setup):
    booking_payload["rooms"].append({"roomId": 2, "qty": 1})
    booking_payload["adults"] = 5
    result = client.post("/api/me/bookings", json=booking_payload, headers=headers())
    assert result.status_code == 201
    booking = result.json()
    assert len(booking["rooms"]) == 2 and booking["totalPrice"] == 525000
    with setup["factory"]() as db:
        db.get(Room, 1).price_per_night = 900000
        db.commit()
    assert client.get(f"/api/me/bookings/{booking['id']}", headers=headers()).json()["totalPrice"] == 525000
    assert len(client.get("/api/host/bookings", headers=headers(3)).json()) == 1


@pytest.mark.parametrize(
    "patch",
    [
        {"checkIn": "2000-01-01"},
        {"checkOut": "2000-01-01"},
        {"checkIn": "not-date"},
        {"adults": 0},
        {"children": -1},
        {"adults": 11},
        {"rooms": []},
        {"rooms": [{"key": "fake", "qty": 1}]},
        {"rooms": [{"key": "room-one", "qty": 0}]},
        {"rooms": [{"key": "room-one", "qty": 1.2}]},
        {"adults": 5},
        {"rooms": [{"key": "room-one", "qty": 1}, {"roomId": 1, "qty": 1}]},
        {"rooms": [{"roomId": 3, "qty": 1}]},
        {"cardNum": "4111111111111111"},
        {"cvv": "123"},
    ],
)
def test_invalid_booking_input(client, headers, booking_payload, patch):
    response = client.post("/api/me/bookings", json={**booking_payload, **patch}, headers=headers())
    assert response.status_code == 422
    assert client.get("/api/me/bookings", headers=headers()).json() == []


def test_rejection_requires_reason_and_releases_inventory(client, headers, booking_payload):
    booking_payload["rooms"] = [{"key": "room-two", "qty": 1}]
    first = client.post("/api/me/bookings", json=booking_payload, headers=headers()).json()
    assert client.post("/api/me/bookings", json=booking_payload, headers=headers(2)).status_code == 409
    url = f"/api/host/bookings/{first['id']}/status"
    assert client.patch(url, json={"status": "rejected"}, headers=headers(3)).status_code == 422
    result = client.patch(url, json={"status": "rejected", "reason": "Room under repair"}, headers=headers(3))
    assert result.status_code == 200 and result.json()["rejectReason"] == "Room under repair"
    assert client.post("/api/me/bookings", json=booking_payload, headers=headers(2)).status_code == 201


def test_checkout_day_is_not_reserved(client, headers, booking_payload):
    booking_payload["rooms"] = [{"key": "room-two", "qty": 1}]
    assert client.post("/api/me/bookings", json=booking_payload, headers=headers()).status_code == 201
    checkout = date.fromisoformat(booking_payload["checkOut"])
    next_stay = {
        **booking_payload,
        "checkIn": checkout.isoformat(),
        "checkOut": (checkout + timedelta(days=2)).isoformat(),
    }
    assert client.post("/api/me/bookings", json=next_stay, headers=headers(2)).status_code == 201


def test_cancel_is_idempotent_and_releases_inventory(client, headers, booking_payload, setup):
    booking = client.post("/api/me/bookings", json=booking_payload, headers=headers()).json()
    url = f"/api/me/bookings/{booking['id']}/cancel"
    assert client.post(url, headers=headers(2)).status_code == 404
    assert client.post(url, headers=headers()).status_code == 200
    assert client.post(url, headers=headers()).status_code == 200
    with setup["factory"]() as db:
        assert db.scalar(select(func.count()).select_from(RoomNight)) == 0
        assert db.scalar(select(Payment)).status == "cancelled"
    assert (
        len(client.get(f"/api/me/bookings/{booking['id']}", headers=headers()).json()["statusHistory"]) == 2
    )


def test_payment_is_pending_and_no_fake_charge(client, headers, booking_payload):
    booking = client.post("/api/me/bookings", json=booking_payload, headers=headers()).json()
    url = f"/api/me/bookings/{booking['id']}/payments"
    payment = client.get(url, headers=headers()).json()[0]
    assert payment["status"] == "pending" and payment["method"] == "pay_at_property"
    assert payment["transactionReference"] is None
    assert client.get(url, headers=headers(2)).status_code == 404


def test_status_machine_and_review_eligibility(client, headers, booking_payload, monkeypatch):
    booking = client.post("/api/me/bookings", json=booking_payload, headers=headers()).json()
    url = f"/api/host/bookings/{booking['id']}/status"
    review = {"bookingId": booking["id"], "rating": 5, "comment": "A good stay", "name": "Forged Name"}
    assert client.post("/api/items/1/reviews", json=review, headers=headers()).status_code == 409
    assert client.patch(url, json={"status": "completed"}, headers=headers(3)).status_code == 409
    assert client.patch(url, json={"status": "confirmed"}, headers=headers(3)).status_code == 200
    assert client.patch(url, json={"status": "checked_in"}, headers=headers(3)).status_code == 409
    checkin = date.fromisoformat(booking_payload["checkIn"])
    monkeypatch.setattr("backend.booking_service.business_today", lambda: checkin)
    assert client.patch(url, json={"status": "checked_in"}, headers=headers(3)).status_code == 200
    assert client.post(f"/api/me/bookings/{booking['id']}/cancel", headers=headers()).status_code == 409
    assert client.patch(url, json={"status": "completed"}, headers=headers(3)).status_code == 409
    monkeypatch.setattr(
        "backend.booking_service.business_today", lambda: date.fromisoformat(booking_payload["checkOut"])
    )
    assert client.patch(url, json={"status": "completed"}, headers=headers(3)).status_code == 200
    assert client.post("/api/items/1/reviews", json=review, headers=headers(2)).status_code == 409
    response = client.post("/api/items/1/reviews", json=review, headers=headers())
    assert (
        response.status_code == 201 and response.json()["name"] == "Account 1" and response.json()["verified"]
    )
    assert client.post("/api/items/1/reviews", json=review, headers=headers()).status_code == 409
    assert client.get("/api/items/1").json()["rating"] == 5


def test_idempotent_booking_retry_and_conflicting_body(client, headers, booking_payload):
    header = {**headers(), "Idempotency-Key": "checkout-request-123"}
    first = client.post("/api/me/bookings", json=booking_payload, headers=header)
    second = client.post("/api/me/bookings", json=booking_payload, headers=header)
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]
    assert (
        client.post(
            "/api/me/bookings", json={**booking_payload, "guestName": "Different Name"}, headers=header
        ).status_code
        == 409
    )


def test_parallel_bookings_do_not_oversell(client, headers, booking_payload, setup):
    booking_payload["rooms"] = [{"roomId": 2, "qty": 1}]
    barrier = Barrier(2)

    def reserve(uid):
        barrier.wait(timeout=10)
        return client.post("/api/me/bookings", json=booking_payload, headers=headers(uid)).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, [1, 2]))
    assert sorted(results) == [201, 409]
    with setup["factory"]() as db:
        assert db.scalar(select(func.count()).select_from(Booking)) == 1
        assert db.scalar(select(func.count()).select_from(BookingLine)) == 1
        assert db.scalar(select(func.count()).select_from(RoomNight)) == 2


def test_parallel_same_idempotency_key_does_not_duplicate(client, headers, booking_payload):
    barrier = Barrier(2)

    def reserve(_):
        barrier.wait(timeout=10)
        return client.post(
            "/api/me/bookings", json=booking_payload, headers={**headers(), "Idempotency-Key": "parallel-key"}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(reserve, range(2)))
    assert sorted(response.status_code for response in responses) == [200, 201]
    assert len({response.json()["id"] for response in responses}) == 1


def test_multi_room_failure_rolls_back_entire_booking(client, headers, booking_payload, setup):
    unavailable = {**booking_payload, "rooms": [{"roomId": 2, "qty": 1}]}
    assert client.post("/api/me/bookings", json=unavailable, headers=headers(2)).status_code == 201
    combined = {**booking_payload, "rooms": [{"roomId": 1, "qty": 1}, {"roomId": 2, "qty": 1}]}
    assert client.post("/api/me/bookings", json=combined, headers=headers()).status_code == 409
    assert client.get("/api/me/bookings", headers=headers()).json() == []
    with setup["factory"]() as db:
        assert db.scalar(select(func.count()).select_from(RoomNight).where(RoomNight.room_id == 1)) == 0


def test_database_unique_constraint_rolls_back_booking_and_payment(client, headers, booking_payload, setup):
    from sqlalchemy import event
    from sqlalchemy.orm import Session

    injected = False

    def duplicate_night(session, *_):
        nonlocal injected
        reservations = [row for row in session.new if isinstance(row, RoomNight) and row.booking_id]
        if reservations and not injected:
            injected = True
            first = reservations[0]
            session.add(
                RoomNight(
                    room_id=first.room_id, unit=first.unit, night=first.night, booking_id=first.booking_id
                )
            )

    event.listen(Session, "before_flush", duplicate_night)
    try:
        response = client.post("/api/me/bookings", json=booking_payload, headers=headers())
        assert response.status_code == 409
    finally:
        event.remove(Session, "before_flush", duplicate_night)
    with setup["factory"]() as db:
        for model in [Booking, BookingLine, RoomNight, Payment]:
            assert db.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.parametrize("days_before,expected", [(3, 210000), (2, 0)])
def test_refund_policy_records_due_without_fake_refund(
    client, headers, booking_payload, setup, monkeypatch, days_before, expected
):
    booking = client.post("/api/me/bookings", json=booking_payload, headers=headers()).json()
    with setup["factory"]() as db:
        payment = db.scalar(select(Payment))
        payment.status = "paid"
        payment.transaction_reference = "test-confirmed-receipt"
        db.commit()
    monkeypatch.setattr(
        "backend.booking_service.business_today",
        lambda: date.fromisoformat(booking_payload["checkIn"]) - timedelta(days=days_before),
    )
    result = client.post(f"/api/me/bookings/{booking['id']}/cancel", headers=headers())
    assert result.json()["refundDue"] == expected
    payment = client.get(f"/api/me/bookings/{booking['id']}/payments", headers=headers()).json()[0]
    assert payment["status"] == ("refund_pending" if expected else "paid")
