"""Independent Phase 1-3 review checks. No application code is patched here.

Regression assertions for defects recorded in PHASE_1_3_REVIEW.md. All databases come from the isolated existing test fixtures.
"""

import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, inspect, select, text
from sqlalchemy.exc import IntegrityError

from backend.config import Settings
from backend.models import AuthSession, HostApplication, User, utcnow

from .conftest import PASSWORD, migrate


def claims_for(setup, uid=1):
    return jwt.decode(
        setup["tokens"][uid],
        setup["settings"].jwt_secret,
        algorithms=["HS256"],
        audience="luxstay-api",
    )


@pytest.mark.parametrize("algorithm", ["HS384", "none"])
def test_jwt_rejects_unapproved_algorithms(setup, client, algorithm):
    key = "" if algorithm == "none" else setup["settings"].jwt_secret
    token = jwt.encode(claims_for(setup), key, algorithm=algorithm)
    response = client.get("/api/me", headers={"Authorization": "Bearer " + token})
    assert response.status_code == 401
    assert token not in response.text


@pytest.mark.parametrize("claim", ["sub", "jti", "ver", "iat", "nbf", "exp", "iss", "aud"])
def test_jwt_requires_all_security_claims(setup, client, claim):
    payload = claims_for(setup)
    payload.pop(claim)
    token = jwt.encode(payload, setup["settings"].jwt_secret, algorithm="HS256")
    assert client.get("/api/me", headers={"Authorization": "Bearer " + token}).status_code == 401


def test_jwt_expiry_and_session_binding_are_checked_independently(setup, client, headers):
    payload = claims_for(setup)
    assert payload["exp"] - payload["iat"] == setup["settings"].jwt_expire_minutes * 60
    future = jwt.encode(
        {**payload, "nbf": utcnow() + timedelta(minutes=5)},
        setup["settings"].jwt_secret,
        algorithm="HS256",
    )
    assert client.get("/api/me", headers={"Authorization": "Bearer " + future}).status_code == 401
    with setup["factory"]() as db:
        session = db.scalar(select(AuthSession).where(AuthSession.user_id == 1))
        session.expires_at = utcnow() - timedelta(seconds=10)
        db.commit()
    assert client.get("/api/me", headers=headers()).status_code == 401


def test_role_claim_or_changed_subject_cannot_override_database_identity(setup, client):
    payload = claims_for(setup)
    token = jwt.encode({**payload, "role": "admin"}, setup["settings"].jwt_secret, algorithm="HS256")
    header = {"Authorization": "Bearer " + token}
    assert client.get("/api/me", headers=header).json()["role"] == "user"
    assert client.get("/api/admin/users", headers=header).status_code == 403
    token = jwt.encode({**payload, "sub": "3"}, setup["settings"].jwt_secret, algorithm="HS256")
    assert client.get("/api/host/homestays", headers={"Authorization": "Bearer " + token}).status_code == 401


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", 2),
        ("user_id", 2),
        ("role", "admin"),
        ("is_active", True),
        ("token_version", 0),
        ("password_hash", "forged"),
    ],
)
def test_profile_cannot_assign_identity_privileges_or_password_hash(setup, client, headers, field, value):
    before = client.get("/api/me/profile", headers=headers(2)).json()
    body = {"display_name": "Profile Probe", "email": "profile.probe@example.com", field: value}
    response = client.put("/api/me/profile", json=body, headers=headers())
    assert response.status_code == 422
    assert client.get("/api/me/profile", headers=headers(2)).json() == before
    with setup["factory"]() as db:
        assert db.get(User, 1).role == "user"
        assert db.get(User, 2).password_hash != "forged"


def test_profile_query_or_path_id_does_not_select_another_account(client, headers):
    before = client.get("/api/me/profile", headers=headers(2)).json()
    body = {"display_name": "Changed Own Profile", "email": "own.profile@example.com"}
    response = client.put("/api/me/profile?user_id=2&id=2", json=body, headers=headers())
    assert response.status_code == 200 and response.json()["id"] == 1
    assert client.put("/api/me/profile/2", json=body, headers=headers()).status_code == 404
    assert client.get("/api/me/profile", headers=headers(2)).json() == before


def test_host_application_cannot_set_applicant_status_or_reviewer(client, headers):
    for forged in [{"user_id": 2}, {"status": "approved"}, {"reviewed_by": 5}]:
        assert client.post("/api/host/apply", json=forged, headers=headers()).status_code == 422
    own = client.post("/api/host/apply", json={}, headers=headers()).json()
    other = client.post("/api/host/apply", json={}, headers=headers(2)).json()
    assert own["id"] != other["id"]
    response = client.get("/api/me/host-application?user_id=2", headers=headers())
    assert response.status_code == 200 and response.json()["user"]["id"] == 1
    url = f"/api/admin/host-applications/{own['id']}/approve"
    assert client.post(url, headers=headers()).status_code == 403
    assert client.post(url, headers=headers(3)).status_code == 403


def test_rejected_application_does_not_grant_host_role(setup, client, headers):
    application = client.post("/api/host/apply", json={}, headers=headers()).json()
    response = client.post(
        f"/api/admin/host-applications/{application['id']}/reject",
        json={"reason": "Missing documents"},
        headers=headers(5),
    )
    assert response.status_code == 200 and response.json()["reviewedBy"] == 5
    assert response.json()["reviewedAt"] is not None
    assert client.get("/api/me", headers=headers()).json()["role"] == "user"
    assert client.get("/api/host/homestays", headers=headers()).status_code == 403
    with setup["factory"]() as db:
        assert db.get(HostApplication, application["id"]).reject_reason == "Missing documents"


def test_disabled_applicant_cannot_be_approved(client, headers):
    application = client.post("/api/host/apply", json={}, headers=headers()).json()
    assert (
        client.patch("/api/admin/users/1", json={"is_active": False}, headers=headers(5)).status_code == 200
    )
    assert (
        client.post(
            f"/api/admin/host-applications/{application['id']}/approve", headers=headers(5)
        ).status_code
        == 409
    )
    assert client.post("/api/host/apply", json={}, headers=headers()).status_code == 401


def test_reactivation_does_not_restore_revoked_tokens(client, headers):
    assert (
        client.patch("/api/admin/users/1", json={"is_active": False}, headers=headers(5)).status_code == 200
    )
    assert client.patch("/api/admin/users/1", json={"is_active": True}, headers=headers(5)).status_code == 200
    assert client.get("/api/me", headers=headers()).status_code == 401
    assert (
        client.post(
            "/api/auth/login", json={"email": "account1@example.com", "password": PASSWORD}
        ).status_code
        == 200
    )


def test_required_production_secret_without_touching_real_env(monkeypatch, tmp_path):
    import backend.config as module

    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValueError, match="JWT_SECRET is required"):
        Settings.from_env()
    assert not (tmp_path / ".local-secret").exists()


@pytest.mark.parametrize("environment", ["prod", "Production"])
def test_unknown_environment_must_fail_closed(monkeypatch, tmp_path, environment):
    import backend.config as module

    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setenv("APP_ENV", environment)
    monkeypatch.setenv("JWT_SECRET", secrets.token_urlsafe(48))
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + (tmp_path / "not-production.db").as_posix())
    with pytest.raises(ValueError):
        Settings.from_env()


def test_invalid_unicode_password_must_be_a_client_error(setup):
    with TestClient(setup["app"], raise_server_exceptions=False) as client:
        response = client.post(
            "/api/auth/register",
            content=json.dumps(
                {"display_name": "Unicode Probe", "email": "surrogate@example.com", "password": "\ud800" * 8},
                ensure_ascii=True,
            ),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code in {400, 422}


def test_malformed_avatar_url_must_be_a_client_error_without_partial_update(setup, client, headers):
    before = client.get("/api/me/profile", headers=headers()).json()
    with TestClient(setup["app"], raise_server_exceptions=False) as probe:
        response = probe.put(
            "/api/me/profile",
            json={"display_name": "Must Roll Back", "email": "rollback@example.com", "avatar": "https://["},
            headers=headers(),
        )
    assert client.get("/api/me/profile", headers=headers()).json() == before
    assert response.status_code == 422


def test_database_enforces_user_role_session_fk_and_application_uniqueness(setup, client, headers):
    with setup["factory"]() as db:
        db.get(User, 1).role = "root"
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
        db.add(AuthSession(id="0" * 64, user_id=999999, expires_at=utcnow() + timedelta(minutes=5)))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()
    assert client.post("/api/host/apply", json={}, headers=headers()).status_code == 201
    with setup["factory"]() as db:
        db.add(HostApplication(user_id=1))
        with pytest.raises(IntegrityError):
            db.flush()
        db.rollback()


@pytest.mark.parametrize("defect", ["missing-email-unique", "missing-owner-fk", "wrong-primary-key"])
def test_legacy_schema_guard_refuses_unsafe_shapes_without_erasing_data(empty_engine, defect):
    migrate(empty_engine, "0001_template")
    with empty_engine.begin() as connection:
        connection.execute(text("DROP TABLE items"))
        if defect == "missing-email-unique":
            connection.execute(text("DROP INDEX ix_users_email"))
        if defect == "wrong-primary-key":
            connection.execute(text("DROP TABLE users"))
            connection.execute(
                text(
                    "CREATE TABLE users (id VARCHAR(20) PRIMARY KEY,email VARCHAR(255) NOT NULL UNIQUE,password_hash VARCHAR(255) NOT NULL,display_name VARCHAR(80) NOT NULL,phone VARCHAR(20) NOT NULL,role VARCHAR(20) NOT NULL,created_at TIMESTAMP NOT NULL)"
                )
            )
        foreign_key = "" if defect == "missing-owner-fk" else " REFERENCES users(id)"
        owner_type = "VARCHAR(20)" if defect == "wrong-primary-key" else "INTEGER"
        connection.execute(
            text(
                f"CREATE TABLE items (id INTEGER PRIMARY KEY,title VARCHAR(160) NOT NULL,description TEXT NOT NULL,price INTEGER NOT NULL,cover_url VARCHAR(255) NOT NULL,status VARCHAR(20) NOT NULL,created_at TIMESTAMP NOT NULL,owner_id {owner_type} NOT NULL{foreign_key})"
            )
        )
        connection.execute(
            text(
                "INSERT INTO users (id,email,password_hash,display_name,phone,role,created_at) VALUES ('42','preserved@example.com','not-a-secret','Preserved','','user','2026-01-01 00:00:00')"
            )
        )
        connection.execute(text("DROP TABLE alembic_version"))
    with pytest.raises(RuntimeError):
        migrate(empty_engine)
    with empty_engine.connect() as connection:
        assert connection.execute(text("SELECT email FROM users")).scalar_one() == "preserved@example.com"
        assert "homestays" not in inspect(connection).get_table_names()


def test_invalid_legacy_role_refuses_upgrade_and_rolls_back_added_columns(empty_engine):
    migrate(empty_engine, "0001_template")
    with empty_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id,email,password_hash,display_name,phone,role,created_at) VALUES (42,'legacy.role@example.com','not-a-secret','Legacy User','','unsupported','2026-01-01 00:00:00')"
            )
        )
    with pytest.raises(RuntimeError, match="unsupported roles"):
        migrate(empty_engine)
    with empty_engine.connect() as connection:
        assert connection.execute(text("SELECT role FROM users WHERE id=42")).scalar_one() == "unsupported"
        assert "avatar" not in {column["name"] for column in inspect(connection).get_columns("users")}
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0001_template"
        )


def test_concurrent_host_apply_and_approval_must_not_deadlock(setup, client, headers):
    if setup["engine"].dialect.name != "postgresql":
        pytest.skip("Row-lock deadlock is PostgreSQL-specific; SQLite serializes transactions")
    application = client.post("/api/host/apply", json={}, headers=headers()).json()
    ready = Barrier(2)

    def synchronize_locks(connection, cursor, statement, parameters, context, executemany):
        sql = " ".join(statement.lower().split())
        if "for update" in sql and "from users " in sql:
            ready.wait(timeout=10)

    event.listen(setup["engine"], "before_cursor_execute", synchronize_locks)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            apply = pool.submit(client.post, "/api/host/apply", json={}, headers=headers())
            approve = pool.submit(
                client.post,
                f"/api/admin/host-applications/{application['id']}/approve",
                headers=headers(5),
            )
            statuses = [apply.result(timeout=30).status_code, approve.result(timeout=30).status_code]
    finally:
        event.remove(setup["engine"], "before_cursor_execute", synchronize_locks)
    assert sorted(statuses) == [200, 409], f"Concurrent request statuses: {statuses}"


@pytest.mark.parametrize(
    "field,value",
    [
        ("auth_rate_limit", 0),
        ("auth_rate_window", -1),
        ("max_body_bytes", 0),
        ("jwt_expire_minutes", 1441),
        ("cors_origins", ("https://example.com/path",)),
        ("cors_origins", ("https://example.com:bad",)),
    ],
)
def test_sensitive_settings_fail_closed(field, value):
    with pytest.raises(ValueError):
        Settings(database_url="sqlite://", jwt_secret=secrets.token_urlsafe(48), **{field: value})


def test_invalid_boolean_environment_rejected(monkeypatch, tmp_path):
    import backend.config as module

    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SERVE_FRONTEND", "tru")
    with pytest.raises(ValueError):
        Settings.from_env()
    assert not (tmp_path / ".local-secret").exists()


@pytest.mark.parametrize(
    "endpoint,body",
    [
        ("/api/auth/login", {"email": "account1@example.com", "password": "\ud800"}),
        ("/api/me/password", {"current_password": "\ud800", "new_password": PASSWORD}),
        ("/api/me/password", {"current_password": PASSWORD, "new_password": "\ud800" * 8}),
    ],
)
def test_invalid_unicode_rejected_across_password_inputs(client, headers, endpoint, body):
    response = client.post(
        endpoint,
        content=json.dumps(body, ensure_ascii=True),
        headers={**headers(), "Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert "ud800" not in response.text


@pytest.mark.parametrize("decisions", [("approve", "approve"), ("approve", "reject"), ("reject", "reject")])
def test_concurrent_admin_decisions_are_serialized(setup, client, headers, decisions):
    if setup["engine"].dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock concurrency")
    application = client.post("/api/host/apply", json={}, headers=headers()).json()
    ready = Barrier(2)

    def synchronize(connection, cursor, statement, parameters, context, executemany):
        sql = " ".join(statement.lower().split())
        if "for update" in sql and "from users " in sql:
            ready.wait(timeout=10)

    def decide(action):
        return client.post(
            f"/api/admin/host-applications/{application['id']}/{action}",
            json={"reason": "Review decision"} if action == "reject" else None,
            headers=headers(5),
        )

    event.listen(setup["engine"], "before_cursor_execute", synchronize)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(decide, decisions))
    finally:
        event.remove(setup["engine"], "before_cursor_execute", synchronize)
    assert sorted(r.status_code for r in results) == [200, 409]
    winner = next(r.json() for r in results if r.status_code == 200)
    with setup["factory"]() as db:
        saved = db.get(HostApplication, application["id"])
        assert saved.status == winner["status"]
        assert db.get(User, 1).role == ("host" if saved.status == "approved" else "user")
