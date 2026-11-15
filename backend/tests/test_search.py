"""Tham số q (tìm kiếm không phân biệt dấu) của các danh sách host/admin."""

from backend.search import fold, matches, tokens


def test_fold_and_match_ignore_case_and_vietnamese_accents():
    assert fold("Đà Lạt") == "da lat"
    assert matches(tokens("da lat"), "Đà Lạt Pine Cabin")
    assert matches(tokens("NGUYEN ha"), "Nguyễn Thu Hà", "0901")
    assert not matches(tokens("hue"), "Đà Lạt")
    assert tokens("   ") == []


def test_host_homestay_search_is_scoped_to_the_host(client, headers):
    found = client.get("/api/host/homestays", params={"q": "homestay 1"}, headers=headers(3)).json()
    assert [h["id"] for h in found] == ["1"]
    assert (
        client.get("/api/host/homestays", params={"q": "đà lạt"}, headers=headers(3)).json()[0]["id"] == "1"
    )
    assert client.get("/api/host/homestays", params={"q": "nowhere"}, headers=headers(3)).json() == []
    # host 4 không tìm thấy homestay của host 3
    assert client.get("/api/host/homestays", params={"q": "homestay 1"}, headers=headers(4)).json() == []
    # không có q thì giữ nguyên hành vi cũ
    assert len(client.get("/api/host/homestays", headers=headers(3)).json()) == 1


def test_host_booking_search_by_guest_and_homestay(client, headers, booking_payload):
    booking_payload["guestName"] = "Nguyễn Thu Hà"
    assert client.post("/api/me/bookings", json=booking_payload, headers=headers()).status_code == 201
    for q in ("nguyen thu ha", "THU HÀ", "homestay 1"):
        assert len(client.get("/api/host/bookings", params={"q": q}, headers=headers(3)).json()) == 1
    assert client.get("/api/host/bookings", params={"q": "khong co"}, headers=headers(3)).json() == []
    assert client.get("/api/host/bookings", params={"q": "nguyen"}, headers=headers(4)).json() == []
    assert (
        client.get("/api/host/bookings", params={"q": "ha", "status": "completed"}, headers=headers(3)).json()
        == []
    )


def test_admin_searches(client, headers, setup):
    from backend.models import User

    # Keep numeric name queries distinct from phone matches across searchable fields.
    with setup["factory"]() as db:
        for uid in (3, 4):
            db.get(User, uid).phone = "0900000000"
        db.commit()
    hosts = client.get("/api/admin/hosts", params={"q": "homestay 2"}, headers=headers(5)).json()
    assert [h["id"] for h in hosts] == [4]  # khớp qua tên homestay của host
    assert [
        h["id"] for h in client.get("/api/admin/hosts", params={"q": "account 3"}, headers=headers(5)).json()
    ] == [3]
    users = client.get(
        "/api/admin/users", params={"q": "account", "page_size": 2, "page": 2}, headers=headers(5)
    ).json()
    assert [u["id"] for u in users] == [3, 4]
    assert (
        len(
            client.get(
                "/api/admin/users", params={"q": "account 5", "role": "admin"}, headers=headers(5)
            ).json()
        )
        == 1
    )
    stays = client.get("/api/admin/homestays", params={"q": "homestay 2"}, headers=headers(5)).json()
    assert [s["id"] for s in stays] == ["2"]
    assert client.get("/api/admin/host-applications", params={"q": "zzz"}, headers=headers(5)).json() == []


def test_search_query_is_length_limited(client, headers):
    assert client.get("/api/host/homestays", params={"q": "x" * 101}, headers=headers(3)).status_code == 422
