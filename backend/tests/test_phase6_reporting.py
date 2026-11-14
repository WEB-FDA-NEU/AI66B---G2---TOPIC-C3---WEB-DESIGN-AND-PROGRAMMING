"""Phase 6 reporting/admin acceptance on both private database engines."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import event, select

from backend.models import Booking, HostApplicationHistory, Payment, Room


def book(client, headers, payload):
    response = client.post("/api/me/bookings", json=payload, headers=headers())
    assert response.status_code == 201
    return response.json()


def test_host_cash_is_not_booking_value_and_lines_not_duplicated(setup, client, headers, booking_payload):
    booking_payload["rooms"] = [{"roomId": 1, "qty": 1}, {"roomId": 2, "qty": 1}]
    b = book(client, headers, booking_payload)
    assert (
        client.patch(
            f"/api/host/bookings/{b['id']}/status", json={"status": "confirmed"}, headers=headers(3)
        ).status_code
        == 200
    )
    dashboard = client.get("/api/host/dashboard", headers=headers(3)).json()
    assert dashboard["periodBookingCount"] == 1 and dashboard["bookingValue"] == 525000
    assert dashboard["payments"]["paidRevenue"] == 0
    assert dashboard["roomTypeCount"] == 2 and dashboard["inventoryCount"] == 3
    assert client.get("/api/host/dashboard", headers=headers(4)).json()["bookingCount"] == 0
    for state, refund, pending, received in [
        ("paid", 0, 0, 525000),
        ("refund_pending", 525000, 525000, 525000),
        ("refunded", 525000, 0, 0),
    ]:
        with setup["factory"]() as db:
            db.scalar(select(Payment)).status = state
            db.get(Booking, b["id"]).refund_due = refund
            db.commit()
        metrics = client.get("/api/host/dashboard", headers=headers(3)).json()["payments"]
        assert metrics["refundPending"] == pending and metrics["paidRevenue"] == received
        assert metrics["platformRevenue"] is None


def test_admin_overview_kpis_and_pagination(client, headers, booking_payload):
    book(client, headers, booking_payload)
    client.post("/api/host/apply", json={}, headers=headers())
    kpi = client.get("/api/admin/overview", headers=headers(5)).json()["kpis"]
    assert kpi["users"] == 5 and kpi["roles"] == {"user": 2, "host": 2, "admin": 1}
    assert kpi["applications"]["pending"] == 1 and kpi["bookingCount"] == 1
    assert kpi["payments"]["paidRevenue"] == 0 and kpi["allBookingValue"] == 210000
    assert kpi["bookingValue"] == 0
    values = client.get(
        "/api/admin/users", params={"role": "host", "page_size": 1, "page": 2}, headers=headers(5)
    ).json()
    assert len(values) == 1 and values[0]["id"] == 4
    assert "password_hash" not in str(values) and "access_token" not in str(values)
    assert client.get("/api/admin/homestays", params={"status": "inactive"}, headers=headers(5)).json() == []
    assert (
        client.patch("/api/admin/users/1", json={"is_active": False}, headers=headers(5)).status_code == 200
    )
    assert client.get("/api/me", headers=headers()).status_code == 401
    assert len(client.get("/api/admin/users", params={"is_active": False}, headers=headers(5)).json()) == 1


@pytest.mark.parametrize(
    "path,params",
    [
        ("/api/admin/users", {"role": "root"}),
        ("/api/admin/users", {"sort": "SQL"}),
        ("/api/admin/users", {"page_size": 101}),
        ("/api/admin/homestays", {"status": "wrong"}),
        ("/api/admin/host-applications", {"page": 0}),
        ("/api/host/dashboard", {"from": "2099-01-02", "to": "2099-01-01"}),
    ],
)
def test_phase6_invalid_queries(client, headers, path, params):
    assert client.get(path, params=params, headers=headers(3 if "/host/" in path else 5)).status_code == 422


def test_application_review_history_survives_resubmission(setup, client, headers):
    a = client.post(
        "/api/host/apply", json={"application_data": {"reason": "First proposal"}}, headers=headers()
    ).json()
    assert (
        client.post(
            f"/api/admin/host-applications/{a['id']}/reject",
            json={"reason": "Missing documents"},
            headers=headers(5),
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/host/apply", json={"application_data": {"reason": "Second proposal"}}, headers=headers()
        ).status_code
        == 201
    )
    pending = client.get(
        "/api/admin/host-applications", params={"status": "pending"}, headers=headers(5)
    ).json()[0]
    assert pending["history"][0]["application_data"] == {"reason": "First proposal"}
    assert pending["history"][0]["rejectReason"] == "Missing documents"
    assert (
        client.post(f"/api/admin/host-applications/{a['id']}/approve", headers=headers(5)).status_code == 200
    )
    with setup["factory"]() as db:
        entries = list(db.scalars(select(HostApplicationHistory).order_by(HostApplicationHistory.id)))
        assert [h.status for h in entries] == ["rejected", "approved"]
        assert entries[1].application_data == {"reason": "Second proposal"}


def test_local_timezone_bucket_and_cohort(setup, client, headers, booking_payload):
    b = book(client, headers, booking_payload)
    with setup["factory"]() as db:
        db.get(Booking, b["id"]).created_at = datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc)
        db.commit()
    values = client.get(
        "/api/host/dashboard", params={"from": "2026-01-02", "to": "2026-01-02"}, headers=headers(3)
    ).json()
    assert values["periodBookingCount"] == 1 and values["series"][0]["bookings"] == 1
    assert (
        client.get(
            "/api/host/dashboard", params={"from": "2026-01-01", "to": "2026-01-01"}, headers=headers(3)
        ).json()["periodBookingCount"]
        == 0
    )


def test_dashboard_and_admin_query_count_is_bounded(setup, client, headers, booking_payload):
    counts = []

    def capture(conn, cursor, statement, params, ctx, many):
        if statement.lstrip().upper().startswith("SELECT"):
            counts.append(statement)

    def query(path, h):
        counts.clear()
        event.listen(setup["engine"], "before_cursor_execute", capture)
        try:
            response = client.get(path, headers=h)
            assert response.status_code == 200
            return len(counts)
        finally:
            event.remove(setup["engine"], "before_cursor_execute", capture)

    book(client, headers, booking_payload)
    before = [query("/api/host/dashboard", headers(3)), query("/api/admin/hosts", headers(5))]
    with setup["factory"]() as db:
        db.get(Room, 1).inventory = 50
        db.commit()
    for _ in range(12):
        book(client, headers, booking_payload)
    after = [query("/api/host/dashboard", headers(3)), query("/api/admin/hosts", headers(5))]
    assert before == after and max(after) < 25
    assert len(client.get("/api/host/dashboard", headers=headers(3)).json()["recentBookings"]) == 10


def test_application_history_migration_preserves_current_review(empty_engine):
    from backend.database import make_session_factory
    from backend.models import HostApplication, HostApplicationHistory, User, utcnow

    from .conftest import migrate

    migrate(empty_engine, "0003_block_unit")
    factory = make_session_factory(empty_engine)
    with factory() as db:
        user = User(
            email="history@example.com", display_name="History", password_hash="not-a-real-credential"
        )
        db.add(user)
        db.flush()
        application = HostApplication(
            user_id=user.id,
            status="rejected",
            application_data={"reason": "Preserve"},
            reject_reason="Documents required",
            reviewed_by=user.id,
            reviewed_at=utcnow(),
        )
        db.add(application)
        db.commit()
        aid = application.id
    migrate(empty_engine)
    with factory() as db:
        row = db.scalar(select(HostApplicationHistory))
        assert row.application_id == aid and row.reject_reason == "Documents required"
        assert row.application_data == {"reason": "Preserve"} and row.reviewed_at is not None
        assert db.get(HostApplication, aid).status == "rejected"
