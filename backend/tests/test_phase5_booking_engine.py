"""Phase 5 acceptance, same private fixtures on SQLite and PostgreSQL."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from backend import schemas
from backend.booking_service import IDEMPOTENCY_WINDOW, create_booking
from backend.models import (
    Booking,
    BookingLine,
    BookingStatusHistory,
    Homestay,
    Payment,
    Room,
    RoomNight,
    User,
    utcnow,
)

from .test_host_admin_catalog import room_payload
from .test_phase4_management import dates, query_dates


def test_disabled_host_quote_search_availability_create_agree(client, headers, booking_payload):
    assert (
        client.patch("/api/admin/users/3", json={"is_active": False}, headers=headers(5)).status_code == 200
    )
    assert 1 not in [i["id"] for i in client.get("/api/items").json()["items"]]
    assert client.get("/api/items/1/availability", params=query_dates(booking_payload)).status_code == 404
    assert client.post("/api/bookings/quote", json=booking_payload).status_code == 404
    assert client.post("/api/me/bookings", json=booking_payload, headers=headers()).status_code == 404


@pytest.mark.parametrize("entity", ["homestay", "room", "zero-price"])
def test_inactive_or_legacy_free_inventory_not_bookable(setup, client, headers, booking_payload, entity):
    with setup["factory"]() as db:
        if entity == "homestay":
            db.get(Homestay, 1).status = "inactive"
        elif entity == "room":
            db.get(Room, 1).status = "inactive"
        else:
            db.get(Room, 1).price_per_night = 0
        db.commit()
    quote = client.post("/api/bookings/quote", json=booking_payload)
    create = client.post("/api/me/bookings", json=booking_payload, headers=headers())
    assert quote.status_code == create.status_code == (404 if entity == "homestay" else 422)
    if entity != "homestay":
        assert "1" not in [r["id"] for r in client.get("/api/items/1").json()["roomTypes"]]
        assert "1" not in [
            r["id"]
            for r in client.get("/api/items/1/availability", params=query_dates(booking_payload)).json()[
                "rooms"
            ]
        ]
    assert client.get("/api/me/bookings", headers=headers()).json() == []


def test_inventory_above_four_matches_search_and_quote(setup, client, headers, booking_payload):
    with setup["factory"]() as db:
        r = db.get(Room, 1)
        r.capacity = 1
        r.inventory = 6
        db.commit()
    body = {**booking_payload, "adults": 6, "rooms": [{"roomId": 1, "qty": 6}]}
    assert 1 in [
        i["id"] for i in client.get("/api/items", params=query_dates(body, guests=6)).json()["items"]
    ]
    quote = client.post("/api/bookings/quote", json=body)
    assert quote.status_code == 200 and quote.json()["capacity"] == 6
    booking = client.post("/api/me/bookings", json=body, headers=headers())
    assert booking.status_code == 201 and booking.json()["totalPrice"] == quote.json()["total"]
    assert client.post("/api/me/bookings", json=body, headers=headers(2)).status_code == 409


@pytest.mark.parametrize(
    "price,qty,nights,subtotal,fee",
    [(1, 1, 1, 1, 0), (10, 1, 1, 10, 1), (11, 3, 2, 66, 3), (100001, 2, 3, 600006, 30000)],
)
def test_quote_decimal_rounding_matches_creation(
    setup, client, headers, booking_payload, price, qty, nights, subtotal, fee
):
    with setup["factory"]() as db:
        room = db.get(Room, 1)
        room.price_per_night = Decimal(price)
        room.inventory = qty
        db.commit()
    body = {
        **booking_payload,
        "checkOut": (date.fromisoformat(booking_payload["checkIn"]) + timedelta(days=nights)).isoformat(),
        "rooms": [{"roomId": 1, "qty": qty}],
        "totalPrice": -999,
        "pricePerNight": 1,
    }
    q = client.post("/api/bookings/quote", json=body).json()
    assert q["roomSubtotal"] == subtotal and q["serviceFee"] == fee and q["total"] == subtotal + fee
    b = client.post("/api/me/bookings", json=body, headers=headers())
    assert b.status_code == 201 and b.json()["totalPrice"] == q["total"]


def test_price_overflow_fails_atomically(setup, client, headers, booking_payload):
    with setup["factory"]() as db:
        r = db.get(Room, 1)
        r.price_per_night = 99999999999
        r.inventory = 100
        db.commit()
    body = {
        **booking_payload,
        "checkOut": (date.fromisoformat(booking_payload["checkIn"]) + timedelta(days=365)).isoformat(),
        "rooms": [{"roomId": 1, "qty": 100}],
    }
    assert client.post("/api/bookings/quote", json=body).status_code == 422
    assert client.post("/api/me/bookings", json=body, headers=headers()).status_code == 422
    with setup["factory"]() as db:
        for model in [Booking, BookingLine, RoomNight, BookingStatusHistory, Payment]:
            assert db.scalar(select(func.count()).select_from(model)) == 0


def test_partial_block_all_surfaces_and_continuous_unit(client, headers, booking_payload):
    start = date.fromisoformat(booking_payload["checkIn"])
    middle = (start + timedelta(days=1)).isoformat()
    for body in [
        dates(booking_payload, unit=1, end_date=middle),
        dates(booking_payload, unit=2, start_date=middle),
    ]:
        assert client.post("/api/host/rooms/1/blocks", json=body, headers=headers(3)).status_code == 201
    assert (
        next(
            r
            for r in client.get("/api/items/1/availability", params=query_dates(booking_payload)).json()[
                "rooms"
            ]
            if r["id"] == "1"
        )["available"]
        == 0
    )
    assert (
        client.get("/api/items", params=query_dates(booking_payload, max_price=100000)).json()["total"] == 0
    )
    assert client.post("/api/bookings/quote", json=booking_payload).status_code == 409
    assert client.post("/api/me/bookings", json=booking_payload, headers=headers()).status_code == 409


@pytest.mark.parametrize("which", ["guest", "key", "reason"])
def test_invalid_unicode_booking_inputs_are_422(client, headers, booking_payload, which):
    body = {**booking_payload}
    path = "/api/me/bookings"
    h = headers()
    if which == "guest":
        body["guestName"] = "\ud800\ud800"
    elif which == "key":
        body["rooms"] = [{"key": "\ud800", "qty": 1}]
    else:
        b = client.post(path, json=body, headers=h).json()
        path = f"/api/host/bookings/{b['id']}/status"
        body = {"status": "rejected", "reason": "\ud800" * 3}
        h = headers(3)
    response = client.request(
        "PATCH" if which == "reason" else "POST",
        path,
        content=json.dumps(body, ensure_ascii=True),
        headers={**h, "Content-Type": "application/json"},
    )
    assert response.status_code == 422 and "ud800" not in response.text


def test_host_detail_filters_pagination_and_customer_isolation(client, headers, booking_payload):
    ids = [
        client.post("/api/me/bookings", json=booking_payload, headers=headers()).json()["id"]
        for _ in range(2)
    ]
    assert client.post(f"/api/me/bookings/{ids[0]}/cancel", headers=headers()).status_code == 200
    for path, h in [("/api/me/bookings", headers()), ("/api/host/bookings", headers(3))]:
        values = client.get(path, params={"status": "pending", "page": 1, "page_size": 1}, headers=h).json()
        assert len(values) == 1 and int(values[0]["id"]) == ids[1]
        assert client.get(path, params={"page": 3, "page_size": 1}, headers=h).json() == []
        assert client.get(path, params={"status": "bad"}, headers=h).status_code == 422
        assert client.get(path, params={"page": 0}, headers=h).status_code == 422
    path = f"/api/host/bookings/{ids[1]}"
    assert client.get(path, headers=headers(3)).json()["bookingId"] == ids[1]
    assert client.get(path, headers=headers(4)).status_code == 404
    assert client.get(path, headers=headers()).status_code == 403
    assert client.get(path).status_code == 401
    assert client.get("/api/host/bookings/999999", headers=headers(3)).status_code == 404
    assert client.get(f"/api/me/bookings/{ids[1]}", headers=headers(2)).status_code == 404
    assert client.post(f"/api/me/bookings/{ids[1]}/cancel", headers=headers(2)).status_code == 404


def test_status_repeat_and_cancel_do_not_duplicate_history(setup, client, headers, booking_payload):
    b = client.post("/api/me/bookings", json=booking_payload, headers=headers()).json()
    path = f"/api/host/bookings/{b['id']}/status"
    assert client.patch(path, json={"status": "confirmed"}, headers=headers(3)).status_code == 200
    assert client.patch(path, json={"status": "confirmed"}, headers=headers(3)).status_code == 409
    cancel = f"/api/me/bookings/{b['id']}/cancel"
    assert client.post(cancel, headers=headers()).status_code == 200
    assert client.post(cancel, headers=headers()).status_code == 200
    assert client.patch(path, json={"status": "confirmed"}, headers=headers(3)).status_code == 409
    with setup["factory"]() as db:
        assert db.scalar(select(func.count()).select_from(BookingStatusHistory)) == 3
        assert db.scalar(select(func.count()).select_from(RoomNight)) == 0
        assert db.scalar(select(Payment)).status == "cancelled"


def test_idempotency_scope_expiry_and_cancelled_replay(setup, client, headers, booking_payload, monkeypatch):
    key = "same-key-per-user"
    first = client.post(
        "/api/me/bookings", json=booking_payload, headers={**headers(), "Idempotency-Key": key}
    ).json()
    other = client.post(
        "/api/me/bookings", json=booking_payload, headers={**headers(2), "Idempotency-Key": key}
    )
    assert other.status_code == 201 and other.json()["id"] != first["id"]
    assert client.post(f"/api/me/bookings/{first['id']}/cancel", headers=headers()).status_code == 200
    replay = client.post(
        "/api/me/bookings", json=booking_payload, headers={**headers(), "Idempotency-Key": key}
    )
    assert replay.status_code == 200 and replay.json()["status"] == "cancelled"
    with setup["factory"]() as db:
        created = db.get(Booking, first["id"]).created_at
    monkeypatch.setattr(
        "backend.booking_service.utcnow", lambda: created + IDEMPOTENCY_WINDOW + timedelta(seconds=1)
    )
    assert (
        client.post(
            "/api/me/bookings", json=booking_payload, headers={**headers(), "Idempotency-Key": key}
        ).status_code
        == 409
    )
    with setup["factory"]() as db:
        assert db.scalar(select(func.count()).select_from(Booking)) == 2


def test_same_key_different_payload_concurrent(client, headers, booking_payload):
    barrier = Barrier(2)

    def book(name):
        barrier.wait(timeout=10)
        return client.post(
            "/api/me/bookings",
            json={**booking_payload, "guestName": name},
            headers={**headers(), "Idempotency-Key": "race-payload"},
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(book, ["Guest One", "Guest Two"])) == [201, 409]


def test_parallel_quantity_inventory_and_no_orphans(setup, client, headers, booking_payload):
    barrier = Barrier(2)

    def book(uid):
        barrier.wait(timeout=10)
        return client.post("/api/me/bookings", json=booking_payload, headers=headers(uid)).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(book, [1, 2])) == [201, 201]
    assert client.post("/api/me/bookings", json=booking_payload, headers=headers()).status_code == 409
    with setup["factory"]() as db:
        assert db.scalar(select(func.count()).select_from(Booking)) == 2
        assert db.scalar(select(func.count()).select_from(BookingLine)) == 2
        assert db.scalar(select(func.count()).select_from(RoomNight)) == 4
        assert db.scalar(select(func.count()).select_from(BookingStatusHistory)) == 2
        assert db.scalar(select(func.count()).select_from(Payment)) == 2


def test_parallel_confirm_vs_cancel_serializes_history(setup, client, headers, booking_payload):
    b = client.post("/api/me/bookings", json=booking_payload, headers=headers()).json()
    barrier = Barrier(2)

    def act(which):
        barrier.wait(timeout=10)
        if which == "cancel":
            return client.post(f"/api/me/bookings/{b['id']}/cancel", headers=headers()).status_code
        return client.patch(
            f"/api/host/bookings/{b['id']}/status", json={"status": "confirmed"}, headers=headers(3)
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        cancel, confirm = list(pool.map(act, ["cancel", "confirm"]))
    assert cancel == 200 and confirm in {200, 409}
    with setup["factory"]() as db:
        assert db.get(Booking, b["id"]).status == "cancelled"
        assert db.scalar(select(func.count()).select_from(RoomNight)) == 0
        entries = list(db.scalars(select(BookingStatusHistory).order_by(BookingStatusHistory.id)))
        assert [e.new_status for e in entries] in [
            ["pending", "cancelled"],
            ["pending", "confirmed", "cancelled"],
        ]
        assert all(entries[i].new_status == entries[i + 1].old_status for i in range(len(entries) - 1))


def test_soft_delete_preserves_booking_history_and_price(setup, client, headers, booking_payload):
    b = client.post("/api/me/bookings", json=booking_payload, headers=headers()).json()
    assert (
        client.put(
            "/api/host/rooms/1", json=room_payload(pricePerNight=987654), headers=headers(3)
        ).status_code
        == 200
    )
    assert client.post(f"/api/me/bookings/{b['id']}/cancel", headers=headers()).status_code == 200
    assert client.delete("/api/host/rooms/1", headers=headers(3)).status_code == 204
    assert client.delete("/api/host/homestays/1", headers=headers(3)).status_code == 204
    saved = client.get(f"/api/me/bookings/{b['id']}", headers=headers()).json()
    assert saved["totalPrice"] == b["totalPrice"] and saved["rooms"] == b["rooms"]
    assert client.get(f"/api/host/bookings/{b['id']}", headers=headers(3)).status_code == 200


def test_refresh_locked_customer_blocks_stale_authorization(setup, booking_payload):
    with setup["factory"]() as stale:
        user = stale.get(User, 1)
        stale.commit()  # Keep the identity map, but release SQLite transaction before another writer.
        with setup["factory"]() as db:
            db.get(User, 1).is_active = False
            db.get(User, 1).token_version += 1
            db.commit()
        with pytest.raises(HTTPException) as exc:
            create_booking(stale, schemas.BookingIn.model_validate(booking_payload), user)
        assert exc.value.status_code == 401
        stale.rollback()


@pytest.mark.parametrize("qty", [101, True, 999999999999999999])
def test_quantity_overflow_or_boolean_rejected(client, headers, booking_payload, qty):
    result = client.post(
        "/api/me/bookings", json={**booking_payload, "rooms": [{"roomId": 1, "qty": qty}]}, headers=headers()
    )
    assert result.status_code == 422
    assert client.get("/api/me/bookings", headers=headers()).json() == []


def test_parallel_duplicate_host_confirm_has_one_history_entry(setup, client, headers, booking_payload):
    booking = client.post("/api/me/bookings", json=booking_payload, headers=headers()).json()
    ready = Barrier(2)

    def confirm(_):
        ready.wait(timeout=10)
        return client.patch(
            f"/api/host/bookings/{booking['id']}/status", json={"status": "confirmed"}, headers=headers(3)
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(confirm, range(2))) == [200, 409]
    with setup["factory"]() as db:
        assert db.scalar(select(func.count()).select_from(BookingStatusHistory)) == 2
        assert db.get(Booking, booking["id"]).status == "confirmed"
        assert db.scalar(select(func.count()).select_from(RoomNight)) == 2


def test_key_retention_dry_run_and_cleanup_preserve_booking(setup, client, headers, booking_payload):
    from backend.idempotency_cleanup import KEY_RETENTION, expire_keys

    key = "retention-policy-key"
    booked = client.post(
        "/api/me/bookings", json=booking_payload, headers={**headers(), "Idempotency-Key": key}
    ).json()
    assert client.post(f"/api/me/bookings/{booked['id']}/cancel", headers=headers()).status_code == 200
    with setup["factory"]() as db:
        db.get(Booking, booked["id"]).created_at = utcnow() - KEY_RETENTION - timedelta(days=1)
        db.commit()
        assert expire_keys(db) == 1
        updated_at = db.get(Booking, booked["id"]).updated_at
        assert db.get(Booking, booked["id"]).idempotency_key == key
        assert expire_keys(db, apply=True) == 1
        assert db.get(Booking, booked["id"]).idempotency_key is None
        assert db.get(Booking, booked["id"]).updated_at == updated_at
        assert db.scalar(select(func.count()).select_from(Booking)) == 1
        assert db.scalar(select(func.count()).select_from(BookingLine)) == 1
        assert db.scalar(select(func.count()).select_from(BookingStatusHistory)) == 2
        assert db.scalar(select(func.count()).select_from(Payment)) == 1
        assert db.get(Booking, booked["id"]).total_price == booked["totalPrice"]
        assert expire_keys(db, apply=True) == 0
    # Outside retention there is deliberately no old-key replay guarantee.
    response = client.post(
        "/api/me/bookings", json=booking_payload, headers={**headers(), "Idempotency-Key": key}
    )
    assert response.status_code == 201 and response.json()["id"] != booked["id"]
