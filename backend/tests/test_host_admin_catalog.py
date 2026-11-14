import pytest

from .conftest import PASSWORD, host_application_payload


def room_payload(**changes):
    return {
        "homestayId": "1",
        "name": "Updated Room",
        "description": "Comfortable room description",
        "capacity": 2,
        "pricePerNight": 100000,
        "inventory": 2,
        "images": ["img/placeholder.svg"],
        **changes,
    }


def test_catalog_filters_pagination_and_real_rooms(client):
    result = client.get("/api/items", params={"q": "Da Lat", "page_size": 1}).json()
    assert result["total"] == 2 and len(result["items"]) == 1
    assert result["items"][0]["roomTypes"][0]["key"] == "room-one"
    assert result["items"][0]["rating"] is None
    assert client.get("/api/items", params={"min_price": 160000}).json()["total"] == 1
    assert client.get("/api/items", params={"max_price": 110000}).json()["total"] == 1
    assert (
        client.get("/api/items", params=[("amenity", "Wi-fi"), ("amenity", "missing")]).json()["total"] == 0
    )
    assert client.get("/api/items", params={"rating": 4.5}).json()["total"] == 0
    assert client.get("/api/items", params={"q": "does-not-exist"}).json()["total"] == 0
    assert client.get("/api/items", params={"sort": "price_desc"}).json()["items"][0]["id"] == 2


def test_homestay_without_rooms_does_not_invent_a_free_price(client, headers):
    payload = {"name": "Not yet bookable", "address": "Da Lat", "description": "Awaiting real room inventory"}
    response = client.post("/api/host/homestays", json=payload, headers=headers(3))
    assert response.status_code == 201
    public = client.get("/api/items/" + response.json()["id"]).json()
    assert public["price"] is None and public["roomTypes"] == []
    assert client.get("/api/items", params={"q": "Not yet bookable"}).json()["total"] == 0


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page_size": 1001},
        {"rating": 6},
        {"sort": "injected"},
        {"min_price": 200, "max_price": 10},
        {"checkin": "2099-01-01"},
    ],
)
def test_invalid_filters(client, params):
    assert client.get("/api/items", params=params).status_code == 422


def test_resource_ownership_and_string_host_ids(client, headers):
    stays = client.get("/api/host/homestays", headers=headers(3)).json()
    assert len(stays) == 1 and stays[0]["id"] == "1"
    rooms = client.get("/api/host/rooms", headers=headers(3)).json()
    assert len(rooms) == 2 and all(room["homestayId"] == "1" for room in rooms)
    for method, path, body in [
        ("get", "/api/host/homestays/2", None),
        ("delete", "/api/host/homestays/2", None),
        ("get", "/api/host/rooms/3", None),
        ("put", "/api/host/rooms/3", room_payload()),
        ("delete", "/api/host/rooms/3", None),
        ("get", "/api/host/rooms?homestay_id=2", None),
    ]:
        assert client.request(method, path, json=body, headers=headers(3)).status_code == 404
    assert (
        client.post("/api/host/rooms", json=room_payload(homestayId="2"), headers=headers(3)).status_code
        == 404
    )


def test_create_update_delete_host_homestay_and_room(client, headers):
    body = {
        "name": "New Homestay",
        "address": "Ninh Binh, Viet Nam",
        "description": "A new homestay description",
        "amenities": ["Wi-fi"],
        "images": ["img/placeholder.svg"],
    }
    created = client.post("/api/host/homestays", json=body, headers=headers(3))
    assert created.status_code == 201
    stay = created.json()
    assert stay["hostId"] == "3"
    assert (
        client.put(
            f"/api/host/homestays/{stay['id']}", json={**body, "name": "Edited Homestay"}, headers=headers(3)
        ).json()["name"]
        == "Edited Homestay"
    )
    room = client.post("/api/host/rooms", json=room_payload(homestayId=stay["id"]), headers=headers(3))
    assert room.status_code == 201
    rid = room.json()["id"]
    assert client.delete(f"/api/host/rooms/{rid}", headers=headers(3)).status_code == 204
    assert client.get(f"/api/host/rooms/{rid}", headers=headers(3)).status_code == 404
    assert client.delete(f"/api/host/homestays/{stay['id']}", headers=headers(3)).status_code == 204
    assert client.get(f"/api/items/{stay['id']}").status_code == 404


def test_blocking_availability_and_unblocking(client, headers, booking_payload):
    block = {
        "start_date": booking_payload["checkIn"],
        "end_date": booking_payload["checkOut"],
        "reason": "Maintenance",
    }
    response = client.post("/api/host/rooms/1/blocks", json=block, headers=headers(3))
    assert response.status_code == 201
    assert client.post("/api/host/rooms/1/blocks", json=block, headers=headers(4)).status_code == 404
    assert client.post("/api/host/rooms/1/blocks", json=block, headers=headers(3)).status_code == 409
    assert client.post("/api/me/bookings", json=booking_payload, headers=headers()).status_code == 409
    availability = client.get(
        "/api/items/1/availability",
        params={"checkin": booking_payload["checkIn"], "checkout": booking_payload["checkOut"]},
    ).json()
    assert next(room for room in availability["rooms"] if room["id"] == "1")["available"] == 0
    block_id = response.json()["id"]
    assert client.delete(f"/api/host/rooms/1/blocks/{block_id}", headers=headers(3)).status_code == 204
    assert client.post("/api/me/bookings", json=booking_payload, headers=headers()).status_code == 201


def test_blocking_cannot_overwrite_reservations(client, headers, booking_payload):
    assert client.post("/api/me/bookings", json=booking_payload, headers=headers()).status_code == 201
    assert (
        client.post(
            "/api/host/rooms/1/blocks",
            json={"start_date": booking_payload["checkIn"], "end_date": booking_payload["checkOut"]},
            headers=headers(3),
        ).status_code
        == 409
    )
    assert (
        client.put(
            "/api/host/rooms/1",
            json=room_payload(blockedDates=[booking_payload["checkIn"]]),
            headers=headers(3),
        ).status_code
        == 409
    )
    assert client.get("/api/host/rooms/1", headers=headers(3)).json()["blockedDates"] == []
    assert client.delete("/api/host/rooms/1", headers=headers(3)).status_code == 409
    assert client.delete("/api/host/homestays/1", headers=headers(3)).status_code == 409


def test_inventory_update_cannot_free_blocked_units(client, headers, booking_payload):
    day = booking_payload["checkIn"]
    assert (
        client.put(
            "/api/host/rooms/1", json=room_payload(inventory=1, blockedDates=[day]), headers=headers(3)
        ).status_code
        == 200
    )
    response = client.put("/api/host/rooms/1", json=room_payload(inventory=2), headers=headers(3))
    assert response.status_code == 200
    assert client.post("/api/me/bookings", json=booking_payload, headers=headers()).status_code == 409


def test_room_capacity_cannot_shrink_with_active_bookings(client, headers, booking_payload):
    assert client.post("/api/me/bookings", json=booking_payload, headers=headers()).status_code == 201
    assert (
        client.put("/api/host/rooms/1", json=room_payload(capacity=1), headers=headers(3)).status_code == 409
    )


def test_application_review_and_role_refresh(client, headers):
    assert (
        client.post(
            "/api/host/apply",
            json=host_application_payload(experience="I own a homestay"),
            headers=headers(),
        ).status_code
        == 201
    )
    assert client.post("/api/host/apply", json=host_application_payload(), headers=headers()).status_code == 409
    applications = client.get("/api/admin/host-applications", headers=headers(5)).json()
    application_id = applications[0]["id"]
    assert (
        client.post(f"/api/admin/host-applications/{application_id}/approve", headers=headers(3)).status_code
        == 403
    )
    result = client.post(f"/api/admin/host-applications/{application_id}/approve", headers=headers(5))
    assert result.status_code == 200 and result.json()["reviewedBy"] == 5
    assert (
        client.post(f"/api/admin/host-applications/{application_id}/approve", headers=headers(5)).status_code
        == 409
    )
    assert client.get("/api/me", headers=headers()).status_code == 401
    session = client.post(
        "/api/auth/login", json={"email": "account1@example.com", "password": PASSWORD}
    ).json()
    assert session["user"]["role"] == "host"
    assert (
        client.get(
            "/api/host/homestays", headers={"Authorization": "Bearer " + session["access_token"]}
        ).status_code
        == 200
    )


def test_reject_application_and_resubmit(client, headers):
    app_id = client.post("/api/host/apply", json=host_application_payload(), headers=headers()).json()["id"]
    assert (
        client.post(
            f"/api/admin/host-applications/{app_id}/reject", json={"reason": " "}, headers=headers(5)
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/admin/host-applications/{app_id}/reject",
            json={"reason": "Missing documents"},
            headers=headers(5),
        ).json()["status"]
        == "rejected"
    )
    assert client.post("/api/host/apply", json=host_application_payload(), headers=headers()).json()["status"] == "pending"


def test_moderation_hides_catalog_and_blocks_new_bookings(client, headers, booking_payload):
    assert (
        client.patch(
            "/api/admin/homestays/1/status",
            json={"status": "inactive", "reason": "Policy violation"},
            headers=headers(5),
        ).status_code
        == 200
    )
    assert client.get("/api/items/1").status_code == 404
    assert client.post("/api/me/bookings", json=booking_payload, headers=headers()).status_code == 404
    assert client.get("/api/host/homestays/1", headers=headers(3)).status_code == 200


def test_admin_cannot_lock_or_demote_self(client, headers):
    assert (
        client.patch("/api/admin/users/5", json={"is_active": False}, headers=headers(5)).status_code == 409
    )
    assert client.patch("/api/admin/users/5", json={"role": "user"}, headers=headers(5)).status_code == 409
    assert client.patch("/api/admin/users/1", json={"role": "host"}, headers=headers(5)).status_code == 422


def test_dashboard_aggregates_only_current_host(client, headers, booking_payload):
    booking = client.post("/api/me/bookings", json=booking_payload, headers=headers()).json()
    assert (
        client.patch(
            f"/api/host/bookings/{booking['id']}/status", json={"status": "confirmed"}, headers=headers(3)
        ).status_code
        == 200
    )
    dashboard = client.get("/api/host/dashboard", headers=headers(3)).json()
    assert (
        dashboard["bookingCount"] == 1
        and dashboard["confirmedRevenue"] == 210000
        and dashboard["completedRevenue"] == 0
    )
    assert client.get("/api/host/dashboard", headers=headers(4)).json()["bookingCount"] == 0
    overview = client.get("/api/admin/overview", headers=headers(5)).json()
    assert len(overview["bookings"]) == 1 and len(overview["users"]) == 5
    hosts = client.get("/api/admin/hosts", headers=headers(5)).json()
    assert len(hosts) == 2 and hosts[0]["bookingCount"] == 1


def test_dashboard_counts_quantity_and_filters_created_date(client, headers, booking_payload):
    booking_payload["rooms"] = [{"roomId": 1, "qty": 2}]
    booking = client.post("/api/me/bookings", json=booking_payload, headers=headers()).json()
    assert (
        client.patch(
            f"/api/host/bookings/{booking['id']}/status", json={"status": "confirmed"}, headers=headers(3)
        ).status_code
        == 200
    )
    future = client.get(
        "/api/host/dashboard",
        params={"from": booking_payload["checkIn"], "to": booking_payload["checkOut"]},
        headers=headers(3),
    ).json()
    assert future["periodBookingCount"] == 0 and future["confirmedRevenue"] == 0
    assert future["occupancy"][0]["roomCount"] == 3 and future["occupancy"][0]["nights"] == 4
    assert future["occupancy"][0]["capacity"] == 9
    assert (
        client.get(
            "/api/host/dashboard", params={"from": "2027-02-02", "to": "2027-01-01"}, headers=headers(3)
        ).status_code
        == 422
    )
