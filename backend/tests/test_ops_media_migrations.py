import base64
import hashlib
import io
import json
from dataclasses import replace

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import inspect, text

from backend.config import Settings
from backend.database import make_engine, make_session_factory
from backend.main import create_app
from backend.models import Homestay, User
from backend.seed import seed_database

from .conftest import ROOT, migrate


def valid_png():
    output = io.BytesIO()
    Image.new("RGB", (16, 16), "green").save(output, format="PNG")
    return output.getvalue()


def test_upload_decodes_raster_and_profile_data_uri(client, headers, setup):
    response = client.post(
        "/api/uploads", files={"file": ("image.png", valid_png(), "image/png")}, headers=headers()
    )
    assert response.status_code == 201
    url = response.json()["url"]
    assert url.startswith("/uploads/") and url.endswith(".jpg")
    file = setup["settings"].upload_dir / url.rsplit("/", 1)[1]
    with Image.open(file) as image:
        assert image.format == "JPEG" and image.size == (16, 16)
    assert client.get(url).status_code == 200
    avatar = "data:image/png;base64," + base64.b64encode(valid_png()).decode()
    result = client.put(
        "/api/me/profile",
        json={"display_name": "Avatar User", "email": "account1@example.com", "avatar": avatar},
        headers=headers(),
    )
    assert result.status_code == 200 and result.json()["avatar"].startswith("/uploads/")


@pytest.mark.parametrize(
    "name,raw,mime,status",
    [
        ("fake.png", b"not an image", "image/png", 415),
        ("test.svg", b'<svg onload="alert(1)"></svg>', "image/svg+xml", 415),
        ("image.png", b"", "image/png", 413),
        ("image.png", b"x" * (5 * 1024 * 1024 + 1), "image/png", 413),
    ],
    ids=["fake-raster", "svg", "empty", "oversize"],
)
def test_invalid_uploads(client, headers, name, raw, mime, status):
    assert (
        client.post("/api/uploads", files={"file": (name, raw, mime)}, headers=headers()).status_code
        == status
    )


def test_upload_requires_auth_and_image_urls_are_not_executable(client, headers):
    assert (
        client.post("/api/uploads", files={"file": ("test.png", valid_png(), "image/png")}).status_code == 401
    )
    for value in [
        "javascript:alert(1)",
        "data:image/svg+xml;base64,PHN2Zz4=",
        "file:///etc/passwd",
        "/uploads/../../secret",
    ]:
        response = client.put(
            "/api/me/profile",
            json={"display_name": "Customer", "email": "account1@example.com", "avatar": value},
            headers=headers(),
        )
        assert response.status_code in {415, 422}


def test_cors_allowlist_and_safe_error_response(client):
    allowed = client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://localhost:5500",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert (
        allowed.status_code == 200
        and allowed.headers["access-control-allow-origin"] == "http://localhost:5500"
    )
    denied = client.options(
        "/api/auth/login",
        headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"},
    )
    assert denied.status_code == 400 and "access-control-allow-origin" not in denied.headers
    password = "sensitive-raw-password"
    response = client.post(
        "/api/auth/register", json={"display_name": "A", "email": "invalid", "password": password}
    )
    assert response.status_code == 422 and password not in response.text and '"input"' not in response.text
    assert (
        response.headers["x-content-type-options"] == "nosniff"
        and response.headers["cache-control"] == "no-store"
    )
    assert client.get("/api/missing-endpoint").status_code == 404


def test_oversized_chunked_body_is_bounded(client, setup):
    settings = replace(setup["settings"], max_body_bytes=64)
    with TestClient(create_app(settings, setup["engine"])) as small:
        response = small.post(
            "/api/auth/login",
            content=iter([b"x" * 40, b"x" * 40]),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 413


def test_production_config_rejects_default_secret_and_sqlite(tmp_path):
    with pytest.raises(ValueError):
        Settings(database_url="sqlite:///bad.db", jwt_secret="dev-secret", environment="production")
    with pytest.raises(ValueError):
        Settings(
            database_url="sqlite:///bad.db", jwt_secret="a-random-test-secret-" * 3, environment="production"
        )
    with pytest.raises(ValueError):
        Settings(
            database_url="postgresql://host/db", jwt_secret="a-random-test-secret-" * 3, cors_origins=("*",)
        )


def test_unmigrated_startup_does_not_create_tables(tmp_path):
    engine = make_engine("sqlite:///" + (tmp_path / "unmigrated.db").as_posix())
    try:
        settings = Settings(
            database_url=str(engine.url),
            jwt_secret="test-secret-" * 4,
            environment="test",
            upload_dir=tmp_path / "uploads",
            serve_frontend=False,
        )
        with TestClient(create_app(settings, engine)) as client:
            assert client.get("/api/health").status_code == 200
            assert client.get("/api/ready").status_code == 503
        assert inspect(engine).get_table_names() == []
    finally:
        engine.dispose()


def test_migration_preserves_legacy_users_items_and_seed_refuses_overwrite(empty_engine):
    engine = empty_engine
    try:
        migrate(engine, "0001_template")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id,email,password_hash,display_name,phone,role,created_at) VALUES (42,'legacy@example.com','old-hash','Legacy User','','user','2026-01-01 00:00:00')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO items (id,title,description,price,cover_url,status,created_at,owner_id) VALUES (51,'Legacy Item','Preserve me',100,'image.png','active','2026-01-01 00:00:00',42)"
                )
            )
            # The original create_all database has no Alembic version table.
            connection.execute(text("DROP TABLE alembic_version"))
        migrate(engine)
        with make_session_factory(engine)() as db:
            user = db.get(User, 42)
            assert user.email == "legacy@example.com" and user.password_hash == "old-hash" and user.is_active
            assert user.updated_at == user.created_at
            assert db.execute(text("SELECT title FROM items WHERE id=51")).scalar_one() == "Legacy Item"
            with pytest.raises(RuntimeError, match="Existing users"):
                seed_database(db, "a-test-password", "test")
    finally:
        engine.dispose()


def test_unknown_existing_database_is_refused_without_data_loss(empty_engine):
    engine = empty_engine
    try:
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE unrelated (id INTEGER PRIMARY KEY, payload TEXT)"))
            connection.execute(text("INSERT INTO unrelated VALUES (1,'Keep this')"))
        with pytest.raises(RuntimeError, match="Unrecognized existing database"):
            migrate(engine)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT payload FROM unrelated")).scalar_one() == "Keep this"
    finally:
        engine.dispose()


def test_seed_is_idempotent_and_does_not_seed_fake_reviews_or_bookings(empty_engine):
    engine = empty_engine
    try:
        migrate(engine)
        with make_session_factory(engine)() as db:
            result = seed_database(db, "Seed-Password-123!", "test")
            assert result["seeded"] and result["homestays"] == 22 and result["rooms"] == 48
            assert seed_database(db, "Another-Password-123!", "test")["seeded"] is False
            assert db.execute(text("SELECT count(*) FROM reviews")).scalar_one() == 0
            assert db.execute(text("SELECT count(*) FROM bookings")).scalar_one() == 0
            assert db.execute(text("SELECT count(*) FROM payments")).scalar_one() == 0
            highest = db.execute(text("SELECT max(id) FROM homestays")).scalar_one()
            host_id = db.execute(
                text("SELECT id FROM users WHERE role='host' ORDER BY id LIMIT 1")
            ).scalar_one()
            next_stay = Homestay(
                host_id=host_id, name="Created after seed", address="Da Lat", city="Da Lat", location="Da Lat"
            )
            db.add(next_stay)
            db.flush()
            assert next_stay.id > highest
            if engine.dialect.name == "sqlite":
                assert db.execute(text("PRAGMA foreign_key_check")).all() == []
            with pytest.raises(RuntimeError, match="forbidden"):
                seed_database(db, "Seed-Password-123!", "production")
    finally:
        engine.dispose()


def test_migrated_metadata_is_in_sync(tmp_path):
    engine = make_engine("sqlite:///" + (tmp_path / "metadata.db").as_posix())
    try:
        migrate(engine)
        config = Config(str(ROOT / "backend/alembic.ini"))
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.check(config)
    finally:
        engine.dispose()


def test_frontend_baseline_and_mock_switch_are_untouched():
    baseline = json.loads((ROOT / "docs/FRONTEND_BASELINE.json").read_text(encoding="utf-8"))
    current = {
        path.as_posix().removeprefix(ROOT.as_posix() + "/"): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (ROOT / "frontend").rglob("*")
        if path.is_file()
    }
    assert current == baseline["files"]
    assert "export const USE_MOCK = true;" in (ROOT / "frontend/js/config.js").read_text(encoding="utf-8")


def test_both_database_engines_pass_alembic_check_and_foreign_keys(setup):
    config = Config(str(ROOT / "backend/alembic.ini"))
    with setup["engine"].begin() as connection:
        config.attributes["connection"] = connection
        command.check(config)
    if setup["engine"].dialect.name == "sqlite":
        with setup["engine"].connect() as connection:
            assert connection.execute(text("PRAGMA foreign_key_check")).all() == []


def test_destructive_downgrade_is_refused(empty_engine):
    migrate(empty_engine)
    config = Config(str(ROOT / "backend/alembic.ini"))
    with pytest.raises(RuntimeError, match="Destructive downgrade"):
        with empty_engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "0001_template")
    with empty_engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0005_pay_events"
        )
