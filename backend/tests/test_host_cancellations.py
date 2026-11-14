from sqlalchemy import select

from backend.models import Homestay, HostApplication, HostCancellation, User


def test_host_self_cancellation_keeps_reason_for_admin(client, headers, setup):
    with setup["factory"]() as db:
        db.add(
            HostApplication(
                user_id=3,
                status="approved",
                application_data={"homestay_name": "Previous Homestay"},
            )
        )
        db.commit()

    response = client.post(
        "/api/me/host/cancel",
        json={"reason": "Tôi không còn kinh doanh homestay."},
        headers=headers(3),
    )
    assert response.status_code == 204

    with setup["factory"]() as db:
        assert db.get(User, 3).role == "user"
        assert db.get(Homestay, 1).status == "inactive"
        cancellation = db.scalar(select(HostCancellation))
        assert cancellation.source == "host"
        assert cancellation.reason == "Tôi không còn kinh doanh homestay."

    notifications = client.get("/api/admin/host-cancellations", headers=headers(5))
    assert notifications.status_code == 200
    assert notifications.json()[0]["host"]["id"] == 3
    assert notifications.json()[0]["reason"] == "Tôi không còn kinh doanh homestay."
    assert all(host["id"] != 3 for host in client.get("/api/admin/hosts", headers=headers(5)).json())

    login = client.post(
        "/api/auth/login",
        json={"email": "account3@example.com", "password": "Test-Password-123!"},
    )
    assert login.status_code == 200
    application = client.post(
        "/api/host/apply",
        json={
            "application_data": {
                "homestay_name": "New Homestay",
                "address": "123 Test Street",
                "province": "Lam Dong",
                "room_count": 2,
                "description": "A comfortable place for future guest stays.",
                "experience": "I have managed guest stays before.",
                "phone": "0912345678",
                "accept_terms": True,
            }
        },
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert application.status_code == 201
    assert application.json()["status"] == "pending"


def test_host_cancellation_is_blocked_by_active_booking(client, headers, booking_payload, setup):
    booking = client.post("/api/me/bookings", json=booking_payload, headers=headers()).json()
    assert booking["status"] == "pending"

    self_cancel = client.post(
        "/api/me/host/cancel", json={"reason": "Tôi muốn hủy quyền Host."}, headers=headers(3)
    )
    admin_cancel = client.post("/api/admin/users/3/cancel-host", headers=headers(5))

    assert self_cancel.status_code == admin_cancel.status_code == 409
    with setup["factory"]() as db:
        assert db.get(User, 3).role == "host"
        assert db.scalar(select(HostCancellation)) is None


def test_admin_can_cancel_host_without_active_bookings(client, headers, setup):
    response = client.post("/api/admin/users/4/cancel-host", headers=headers(5))
    assert response.status_code == 204

    with setup["factory"]() as db:
        assert db.get(User, 4).role == "user"
        assert db.get(Homestay, 2).status == "inactive"
        cancellation = db.scalar(select(HostCancellation))
        assert cancellation.source == "admin"
        assert cancellation.actor_id == 5

    assert client.get("/api/admin/host-cancellations", headers=headers(5)).json() == []
    assert client.post("/api/admin/users/1/cancel-host", headers=headers(5)).status_code == 409
