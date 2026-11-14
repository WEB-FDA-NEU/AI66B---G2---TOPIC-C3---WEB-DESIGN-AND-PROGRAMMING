import secrets
from datetime import timedelta

import jwt
import pytest
from sqlalchemy import select

from backend.models import AuthSession, User, utcnow
from backend.security import verify_password

from .conftest import PASSWORD


def test_registration_login_profile_and_logout(client):
    payload = {
        "display_name": " New Customer ",
        "email": " New.User@Example.com ",
        "phone": "0912345678",
        "password": PASSWORD,
    }
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 201
    session = response.json()
    assert session["user"]["display_name"] == "New Customer"
    assert session["user"]["email"] == "new.user@example.com"
    assert session["user"]["role"] == "user"
    assert (
        "password" not in response.text and "hash" not in response.text and "credential" not in response.text
    )
    header = {"Authorization": "Bearer " + session["access_token"]}
    assert client.get("/api/me", headers=header).status_code == 200
    assert client.get("/api/me/profile", headers=header).json() == session["user"]
    assert client.post("/api/auth/logout", headers=header).status_code == 204
    assert client.get("/api/me", headers=header).status_code == 401
    login = client.post("/api/auth/login", json={"email": "NEW.USER@example.com", "password": PASSWORD})
    assert login.status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"role": "admin"},
        {"is_active": True},
        {"display_name": " "},
        {"phone": "1234"},
        {"email": "not-email"},
        {"password": "short"},
        {"password": "a" * 129},
    ],
)
def test_registration_rejects_invalid_or_privileged_fields(client, payload):
    value = {"display_name": "Customer", "email": "customer@example.com", "password": PASSWORD, **payload}
    result = client.post("/api/auth/register", json=value)
    assert result.status_code == 422
    assert PASSWORD not in result.text


def test_duplicate_email_case_insensitive(client):
    assert (
        client.post(
            "/api/auth/register",
            json={"display_name": "Customer", "email": "ACCOUNT1@EXAMPLE.COM", "password": PASSWORD},
        ).status_code
        == 409
    )


def test_host_registration_is_pending_not_privilege_escalation(client):
    result = client.post(
        "/api/auth/register",
        json={
            "display_name": "Applicant",
            "email": "applicant@example.com",
            "password": PASSWORD,
            "role": "host",
        },
    )
    assert result.status_code == 201 and result.json()["user"]["role"] == "user"
    header = {"Authorization": "Bearer " + result.json()["access_token"]}
    assert client.get("/api/host/homestays", headers=header).status_code == 403
    assert client.get("/api/me/host-application", headers=header).json()["status"] == "pending"


@pytest.mark.parametrize("uid", [1, 2, 3, 4])
def test_admin_endpoints_reject_other_roles(client, headers, uid):
    for path in ["overview", "hosts", "users", "homestays", "host-applications"]:
        assert client.get("/api/admin/" + path, headers=headers(uid)).status_code == 403


@pytest.mark.parametrize(
    "path",
    ["/api/me", "/api/me/bookings", "/api/host/homestays", "/api/admin/overview", "/api/me/host-application"],
)
def test_missing_token_is_401(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer mock-token"}).status_code == 401


def test_unicode_passwords_are_not_truncated(client):
    first = "界" * 40 + "A"
    second = "界" * 40 + "B"
    response = client.post(
        "/api/auth/register",
        json={"display_name": "Unicode", "email": "unicode@example.com", "password": first},
    )
    assert response.status_code == 201
    assert (
        client.post("/api/auth/login", json={"email": "unicode@example.com", "password": second}).status_code
        == 401
    )
    assert (
        client.post("/api/auth/login", json={"email": "unicode@example.com", "password": first}).status_code
        == 200
    )


def test_password_change_revokes_all_sessions(client, headers):
    another = client.post(
        "/api/auth/login", json={"email": "account1@example.com", "password": PASSWORD}
    ).json()["access_token"]
    assert (
        client.post(
            "/api/me/password",
            json={"current_password": "wrong", "new_password": "New-Password-123!"},
            headers=headers(),
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/me/password",
            json={"current_password": PASSWORD, "new_password": PASSWORD},
            headers=headers(),
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/me/password",
            json={"current_password": PASSWORD, "new_password": "New-Password-123!"},
            headers=headers(),
        ).status_code
        == 204
    )
    assert client.get("/api/me", headers=headers()).status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer " + another}).status_code == 401
    assert (
        client.post(
            "/api/auth/login", json={"email": "account1@example.com", "password": PASSWORD}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login", json={"email": "account1@example.com", "password": "New-Password-123!"}
        ).status_code
        == 200
    )


def test_profile_update_and_mass_assignment(client, headers):
    payload = {"display_name": "Updated Person", "email": "updated@example.com", "phone": "0912345678"}
    assert (
        client.put("/api/me/profile", json={**payload, "role": "admin"}, headers=headers()).status_code == 422
    )
    assert (
        client.put(
            "/api/me/profile", json={**payload, "email": "account2@example.com"}, headers=headers()
        ).status_code
        == 409
    )
    result = client.put("/api/me/profile", json=payload, headers=headers())
    assert result.status_code == 200 and result.json()["display_name"] == "Updated Person"
    assert client.get("/api/me", headers=headers(2)).json()["display_name"] == "Account 2"


def test_logout_only_revokes_current_session(client, headers):
    login = client.post(
        "/api/auth/login", json={"email": "account1@example.com", "password": PASSWORD}
    ).json()
    assert client.post("/api/auth/logout", headers=headers()).status_code == 204
    assert (
        client.get("/api/me", headers={"Authorization": "Bearer " + login["access_token"]}).status_code == 200
    )


def test_forged_expired_wrong_audience_and_disabled_user(setup, client, headers):
    settings = setup["settings"]
    claims = jwt.decode(setup["tokens"][1], settings.jwt_secret, algorithms=["HS256"], audience="luxstay-api")
    for patch in [
        {"exp": utcnow() - timedelta(minutes=1)},
        {"aud": "other"},
        {"iss": "other"},
        {"jti": secrets.token_urlsafe(32)},
        {"sub": "-1"},
        {"ver": 99},
    ]:
        token = jwt.encode({**claims, **patch}, settings.jwt_secret, algorithm="HS256")
        assert client.get("/api/me", headers={"Authorization": "Bearer " + token}).status_code == 401
    forged = jwt.encode(claims, secrets.token_urlsafe(48), algorithm="HS256")
    assert client.get("/api/me", headers={"Authorization": "Bearer " + forged}).status_code == 401
    assert (
        client.patch("/api/admin/users/1", json={"is_active": False}, headers=headers(5)).status_code == 200
    )
    assert client.get("/api/me", headers=headers()).status_code == 401
    assert (
        client.post(
            "/api/auth/login", json={"email": "account1@example.com", "password": PASSWORD}
        ).status_code
        == 401
    )


def test_sessions_store_digest_not_raw_token(setup):
    with setup["factory"]() as db:
        sessions = db.scalars(select(AuthSession)).all()
        assert sessions and all(len(row.id) == 64 for row in sessions)
        assert all(setup["tokens"][1] != row.id for row in sessions)
        assert db.get(User, 1).password_hash.startswith("$argon2id$")


def test_invalid_credentials_have_same_message(client):
    responses = [
        client.post("/api/auth/login", json={"email": email, "password": "wrong"})
        for email in ["missing@example.com", "account1@example.com"]
    ]
    assert [response.status_code for response in responses] == [401, 401]
    assert responses[0].json() == responses[1].json()


def test_legacy_bcrypt_does_not_silently_truncate():
    import bcrypt

    password = "a" * 72
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    assert verify_password(password, hashed)
    assert not verify_password(password + "different", hashed)


def test_legacy_bcrypt_login_upgrades_to_argon2(client, setup):
    import bcrypt

    with setup["factory"]() as db:
        db.get(User, 1).password_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
        db.commit()
    assert (
        client.post(
            "/api/auth/login", json={"email": "account1@example.com", "password": PASSWORD}
        ).status_code
        == 200
    )
    with setup["factory"]() as db:
        assert db.get(User, 1).password_hash.startswith("$argon2id$")


def test_rate_limiting_persists_across_app_instances(setup, client):
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from backend.main import create_app

    setup["app"].state.settings = replace(setup["settings"], auth_rate_limit=2)
    body = {"email": "limited@example.com", "password": "wrong"}
    assert client.post("/api/auth/login", json=body).status_code == 401
    assert client.post("/api/auth/login", json=body).status_code == 401
    with TestClient(create_app(setup["app"].state.settings, setup["engine"])) as second:
        response = second.post("/api/auth/login", json=body)
    assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0
