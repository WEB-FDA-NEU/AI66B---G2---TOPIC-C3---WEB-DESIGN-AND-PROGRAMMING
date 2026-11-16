from datetime import datetime, timezone

import pytest
from sqlalchemy import event

from backend.models import Booking, Homestay, Room, User


def test_admin_period_uses_full_cohort_and_vietnam_day(setup, client, headers, booking_payload):
    response = client.post("/api/me/bookings", json=booking_payload, headers=headers())
    assert response.status_code == 201
    stamp = datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc)
    with setup["factory"]() as db:
        db.get(Booking, response.json()["id"]).created_at = stamp
        for n in range(105):
            db.add(
                User(
                    email=f"period{n}@example.com",
                    display_name="Period User",
                    password_hash="not-a-login-fixture",
                    created_at=stamp,
                )
            )
        db.commit()
    overview = client.get(
        "/api/admin/overview", params={"from": "2026-01-02", "to": "2026-01-02"}, headers=headers(5)
    )
    assert overview.status_code == 200
    data = overview.json()
    assert len(data["users"]) == 100 and data["kpis"]["users"] == 110
    assert data["period"]["newUsers"] == 105 and data["period"]["newBookings"] == 1
    assert data["period"]["series"] == [{"date": "2026-01-02", "users": 105, "bookings": 1}]
    assert data["period"]["provinces"] == [{"name": "Da Lat", "bookings": 1}]
    previous = client.get(
        "/api/admin/overview", params={"from": "2026-01-01", "to": "2026-01-01"}, headers=headers(5)
    ).json()
    assert previous["period"]["newUsers"] == previous["period"]["newBookings"] == 0


def test_host_occupancy_summary_includes_properties_outside_projection(setup, client, headers):
    with setup["factory"]() as db:
        for n in range(101):
            stay = Homestay(
                host_id=3,
                name=f"Extra {n}",
                description="Extra property",
                address="Da Lat",
                location="Da Lat",
                city="Da Lat",
            )
            db.add(stay)
            db.flush()
            db.add(
                Room(
                    homestay_id=stay.id,
                    name=f"Extra Room {n}",
                    key=f"extra-{n}",
                    description="Extra room",
                    capacity=2,
                    inventory=2,
                    price_per_night=100000,
                )
            )
        db.commit()
    response = client.get(
        "/api/host/dashboard", params={"from": "2026-01-02", "to": "2026-01-02"}, headers=headers(3)
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["occupancy"]) == 100 and data["inventoryCount"] == 205
    assert data["occupancySummary"] == {"nights": 0, "actualNights": 0, "capacity": 205, "occupancy": 0}


@pytest.mark.parametrize(
    "params",
    [
        {"from": "2026-02-02", "to": "2026-01-01"},
        {"from": "2024-01-01", "to": "2026-01-01"},
        {"from": "invalid"},
    ],
)
def test_admin_report_rejects_invalid_window(client, headers, params):
    assert client.get("/api/admin/overview", params=params, headers=headers(5)).status_code == 422


def test_admin_report_query_count_does_not_scale_with_users(setup, client, headers):
    def count_queries():
        statements = []

        def capture(conn, cursor, statement, parameters, context, many):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        event.listen(setup["engine"], "before_cursor_execute", capture)
        try:
            assert client.get("/api/admin/overview", headers=headers(5)).status_code == 200
        finally:
            event.remove(setup["engine"], "before_cursor_execute", capture)
        return len(statements)

    before = count_queries()
    with setup["factory"]() as db:
        db.add_all(
            [
                User(
                    email=f"bounded{n}@example.com", display_name="User", password_hash="not-a-login-fixture"
                )
                for n in range(105)
            ]
        )
        db.commit()
    assert count_queries() == before
