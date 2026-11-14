"""Phase 4 regression and acceptance tests, isolated SQLite/PostgreSQL fixtures."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from threading import Barrier

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError

from backend.models import Booking, Homestay, Room, RoomBlock, RoomNight, User
from backend.security import hash_password

from .conftest import migrate
from .test_host_admin_catalog import room_payload

STAY = {"name": "Phase Four Stay", "address": "Da Lat, Viet Nam", "description": "Real managed homestay"}


def dates(payload, **extra):
    return {"start_date": payload["checkIn"], "end_date": payload["checkOut"], **extra}


def query_dates(payload, **extra):
    return {"checkin": payload["checkIn"], "checkout": payload["checkOut"], **extra}


@pytest.mark.parametrize("uid,status", [(None, 401), (1, 403), (5, 403), (4, 404)])
def test_write_roles_and_cross_host_ownership(client, headers, uid, status):
    h = headers(uid) if uid else {}
    assert client.put("/api/host/homestays/1", json=STAY, headers=h).status_code == status
    assert client.put("/api/host/rooms/1", json=room_payload(), headers=h).status_code == status


@pytest.mark.parametrize(
    "body",
    [
        {"host_id": 4},
        {"hostId": 4},
        {"name": "x"},
        {"description": "x"},
        {"address": "x"},
        {"name": "x" * 161},
        {"status": "deleted"},
        {"amenities": ["x"] * 41},
    ],
)
def test_homestay_invalid_or_privileged_fields(client, headers, body):
    assert client.post("/api/host/homestays", json={**STAY, **body}, headers=headers(3)).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"capacity": 0},
        {"capacity": 51},
        {"capacity": True},
        {"inventory": 0},
        {"inventory": -1},
        {"inventory": 101},
        {"pricePerNight": 0},
        {"pricePerNight": -1},
        {"pricePerNight": "NaN"},
        {"host_id": 4},
        {"status": "deleted"},
    ],
)
def test_room_invalid_inputs(client, headers, body):
    assert client.post("/api/host/rooms", json=room_payload(**body), headers=headers(3)).status_code == 422


def test_inactive_status_visibility_and_moderation(client, headers):
    assert (
        client.put("/api/host/rooms/1", json=room_payload(status="inactive"), headers=headers(3)).status_code
        == 200
    )
    assert "1" not in [r["id"] for r in client.get("/api/items/1").json()["roomTypes"]]
    # An old frontend payload without status must not accidentally reactivate it.
    assert (
        client.put("/api/host/rooms/1", json=room_payload(), headers=headers(3)).json()["status"]
        == "inactive"
    )
    assert (
        client.put(
            "/api/host/homestays/1", json={**STAY, "status": "inactive"}, headers=headers(3)
        ).status_code
        == 200
    )
    assert client.get("/api/items/1").status_code == 404
    assert 1 not in [v["id"] for v in client.get("/api/items").json()["items"]]
    assert (
        client.put("/api/host/homestays/1", json={**STAY, "status": "active"}, headers=headers(3)).status_code
        == 200
    )
    assert (
        client.patch(
            "/api/admin/homestays/1/status",
            json={"status": "inactive", "reason": "Safety review"},
            headers=headers(5),
        ).status_code
        == 200
    )
    assert (
        client.put("/api/host/homestays/1", json={**STAY, "status": "active"}, headers=headers(3)).status_code
        == 409
    )
    assert client.put("/api/host/homestays/1", json=STAY, headers=headers(3)).json()["status"] == "inactive"
    assert (
        client.patch(
            "/api/admin/homestays/1/status",
            json={"status": "active", "reason": "Review cleared"},
            headers=headers(5),
        ).status_code
        == 200
    )
    assert client.put("/api/host/homestays/1", json=STAY, headers=headers(3)).json()["status"] == "active"


def test_search_guests_children_and_injection(client, booking_payload):
    assert client.get("/api/items", params={"guests": 9}).json()["total"] == 0
    assert client.get("/api/items", params={"guests": 7}).json()["total"] == 1
    assert client.get("/api/items", params={"guests": 7, "children": 2}).json()["total"] == 0
    assert client.get("/api/items", params={"q": "' OR 1=1 --"}).json()["total"] == 0
    assert client.get("/api/items", params={"amenity": "Wi-fi' OR 1=1 --"}).json()["total"] == 0
    result = client.get("/api/items", params=query_dates(booking_payload, guests=7))
    assert result.status_code == 200 and result.json()["total"] == 1


@pytest.mark.parametrize(
    "params",
    [
        {"children": -1},
        {"children": 7},
        {"guests": 0},
        {"guests": 17},
        {"checkin": "bad", "checkout": "2099-01-02"},
        {"checkin": "2099-01-02", "checkout": "2099-01-01"},
        {"page_size": 0},
        {"min_price": "NaN"},
        {"rating": "NaN"},
        {"amenity": ["x"] * 41},
    ],
)
def test_phase4_invalid_queries(client, params):
    assert client.get("/api/items", params=params).status_code == 422


def test_availability_search_prices_follow_free_rooms(client, headers, booking_payload):
    assert (
        client.post(
            "/api/me/bookings",
            json={**booking_payload, "rooms": [{"roomId": 1, "qty": 2}]},
            headers=headers(),
        ).status_code
        == 201
    )
    result = client.get("/api/items", params=query_dates(booking_payload)).json()
    stay = next(i for i in result["items"] if i["id"] == 1)
    assert stay["price"] == 150000 and [r["id"] for r in stay["roomTypes"]] == ["2"]
    assert (
        client.get("/api/items", params=query_dates(booking_payload, max_price=110000)).json()["total"] == 0
    )
    assert client.get("/api/items", params=query_dates(booking_payload, guests=5)).json()["total"] == 0
    assert (
        client.post("/api/host/rooms/2/blocks", json=dates(booking_payload), headers=headers(3)).status_code
        == 201
    )
    assert 1 not in [
        i["id"] for i in client.get("/api/items", params=query_dates(booking_payload)).json()["items"]
    ]
    # Checkout is exclusive, adjacent stays remain available.
    next_in = booking_payload["checkOut"]
    next_out = (date.fromisoformat(next_in) + timedelta(days=1)).isoformat()
    assert 1 in [
        i["id"]
        for i in client.get("/api/items", params={"checkin": next_in, "checkout": next_out}).json()["items"]
    ]


def test_partial_blocks_update_conflict_rollback_and_growth(client, headers, booking_payload):
    path = "/api/host/rooms/1/blocks"
    created = client.post(path, json=dates(booking_payload, unit=2), headers=headers(3))
    assert created.status_code == 201 and created.json()["scope"] == "unit"
    bid = created.json()["id"]
    url = f"{path}/{bid}"
    assert client.get("/api/host/rooms/1", headers=headers(3)).json()["blockedDates"] == []
    room = client.get("/api/host/rooms/1", headers=headers(3)).json()
    assert room["blocks"][0]["unit"] == 2
    assert (
        client.put(
            "/api/host/rooms/1", json=room_payload(inventory=3, blockedDates=[]), headers=headers(3)
        ).status_code
        == 200
    )
    av = client.get("/api/items/1/availability", params=query_dates(booking_payload)).json()
    assert next(r for r in av["rooms"] if r["id"] == "1")["available"] == 2
    assert (
        client.put("/api/host/rooms/1", json=room_payload(inventory=1), headers=headers(3)).status_code == 409
    )
    assert client.put(url, json=dates(booking_payload, unit=2), headers=headers(4)).status_code == 404
    assert client.post("/api/me/bookings", json=booking_payload, headers=headers()).status_code == 201
    assert client.put(url, json=dates(booking_payload, unit=1), headers=headers(3)).status_code == 409
    saved = client.get(path, headers=headers(3)).json()
    assert saved[0]["id"] == bid and saved[0]["unit"] == 2
    changed = client.put(url, json=dates(booking_payload, unit=3), headers=headers(3))
    assert changed.status_code == 200 and changed.json()["id"] == bid
    assert client.delete(url, headers=headers(3)).status_code == 204
    assert client.get(path, headers=headers(3)).json() == []


@pytest.mark.parametrize("change", [{"unit": 0}, {"unit": 3}, {"unit": True}, {"end_date": "2000-01-01"}])
def test_invalid_block_scope_and_dates(client, headers, booking_payload, change):
    assert (
        client.post(
            "/api/host/rooms/1/blocks", json=dates(booking_payload, **change), headers=headers(3)
        ).status_code
        == 422
    )


def test_whole_stay_units_cannot_switch_mid_stay(client, headers, booking_payload):
    start = date.fromisoformat(booking_payload["checkIn"])
    middle = (start + timedelta(days=1)).isoformat()
    for body in [
        dates(booking_payload, unit=1, end_date=middle),
        dates(booking_payload, unit=2, start_date=middle),
    ]:
        assert client.post("/api/host/rooms/1/blocks", json=body, headers=headers(3)).status_code == 201
    av = client.get("/api/items/1/availability", params=query_dates(booking_payload)).json()
    assert next(r for r in av["rooms"] if r["id"] == "1")["available"] == 0
    stay = next(
        s
        for s in client.get("/api/items", params=query_dates(booking_payload)).json()["items"]
        if s["id"] == 1
    )
    assert stay["price"] == 150000


def test_search_pagination_sql_and_bounded_queries(setup, client):
    with setup["factory"]() as db:
        for i in range(10):
            stay = Homestay(
                host_id=3,
                name=f"Batch Stay {i}",
                address="Da Lat",
                location="Da Lat",
                city="Da Lat",
                amenities=["Wi-fi"],
            )
            db.add(stay)
            db.flush()
            db.add(
                Room(
                    homestay_id=stay.id,
                    key=f"batch-{i}",
                    name="Batch Room",
                    price_per_night=300000 + i,
                    capacity=2,
                    inventory=1,
                )
            )
        db.commit()
    queries = []

    def capture(conn, cursor, sql, params, ctx, many):
        if sql.lstrip().upper().startswith("SELECT"):
            queries.append(sql)

    event.listen(setup["engine"], "before_cursor_execute", capture)
    try:
        a = client.get("/api/items", params={"page_size": 1, "sort": "price_asc", "amenity": "Wi-fi"}).json()
        small = len(queries)
        queries.clear()
        b = client.get("/api/items", params={"page_size": 20, "sort": "price_asc", "amenity": "Wi-fi"}).json()
        large = len(queries)
    finally:
        event.remove(setup["engine"], "before_cursor_execute", capture)
    assert small == large == 5
    assert len(a["items"]) == 1 and len(b["items"]) == 12 and b["total"] == 12
    prices = [s["price"] for s in b["items"]]
    assert prices == sorted(prices)
    assert (
        client.get("/api/items", params={"page": 2, "page_size": 1, "sort": "price_asc"}).json()["items"][0][
            "id"
        ]
        != a["items"][0]["id"]
    )
    assert client.get("/api/items", params={"page": 99999}).json()["items"] == []
    assert any("LIMIT" in sql and "OFFSET" in sql for sql in queries)


def test_rating_sort_uses_real_reviews(setup, client, headers, booking_payload):
    booking = client.post("/api/me/bookings", json=booking_payload, headers=headers()).json()
    with setup["factory"]() as db:
        db.get(Booking, booking["id"]).status = "completed"
        db.commit()
    assert (
        client.post(
            "/api/items/1/reviews",
            json={"bookingId": booking["id"], "rating": 5, "comment": "Excellent real stay"},
            headers=headers(),
        ).status_code
        == 201
    )
    values = client.get("/api/items", params={"sort": "rating_desc"}).json()["items"]
    assert values[0]["id"] == 1 and values[0]["rating"] == 5 and values[0]["review_count"] == 1
    assert values[1]["rating"] is None


def test_parallel_block_and_booking_preserve_inventory(client, headers, booking_payload, setup):
    barrier = Barrier(2)

    def act(kind):
        barrier.wait(timeout=10)
        if kind == "block":
            return client.post(
                "/api/host/rooms/1/blocks", json=dates(booking_payload), headers=headers(3)
            ).status_code
        return client.post("/api/me/bookings", json=booking_payload, headers=headers()).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(act, ["block", "booking"]))
    assert sorted(statuses) == [201, 409]
    with setup["factory"]() as db:
        rows = list(db.scalars(select(RoomNight).where(RoomNight.room_id == 1)))
        assert len({(r.unit, r.night) for r in rows}) == len(rows)
        assert all(r.block_id is not None for r in rows) or all(r.booking_id is not None for r in rows)


def test_v3_upgrade_preserves_existing_blocks_and_ledger(empty_engine):
    migrate(empty_engine, "0002_luxstay")
    from backend.database import make_session_factory

    factory = make_session_factory(empty_engine)
    with factory() as db:
        user = User(
            email="migration@example.com",
            display_name="Migration Host",
            password_hash=hash_password("Migration-Password-123"),
            role="host",
        )
        db.add(user)
        db.flush()
        stay = Homestay(
            host_id=user.id, name="Preserved Stay", address="Da Lat", city="Da Lat", location="Da Lat"
        )
        db.add(stay)
        db.flush()
        room = Room(
            homestay_id=stay.id,
            key="preserve",
            name="Preserved Room",
            price_per_night=123000,
            capacity=2,
            inventory=1,
        )
        db.add(room)
        db.flush()
        db.execute(
            text(
                "INSERT INTO room_blocks (id,room_id,start_date,end_date,reason,created_by,created_at) VALUES (99,:room,'2099-01-01','2099-01-02','Preserved',:actor,'2026-01-01 00:00:00+00:00')"
            ),
            {"room": room.id, "actor": user.id},
        )
        db.add(RoomNight(room_id=room.id, unit=1, night=date(2099, 1, 1), block_id=99))
        db.commit()
    migrate(empty_engine)
    with factory() as db:
        block = db.get(RoomBlock, 99)
        assert block.unit is None and block.reason == "Preserved"
        assert db.scalar(select(func.count()).select_from(RoomNight)) == 1
        block.unit = 0
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
        assert db.get(RoomBlock, 99).unit is None
