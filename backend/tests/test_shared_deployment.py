import json
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.bootstrap_admin import bootstrap_admin
from backend.main import create_app
from backend.models import User
from backend.schemas import RegisterIn


def test_shared_runtime_configuration_contains_only_public_values(setup):
    settings = replace(setup["settings"], serve_frontend=True)
    with TestClient(create_app(settings, setup["engine"])) as client:
        response = client.get("/js/runtime-config.js")
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        payload = json.loads(
            response.text.removeprefix("export const deployment = ").strip().removesuffix(";")
        )
        assert payload == {"mode": "shared", "apiBase": "/api"}
        assert settings.jwt_secret not in response.text
        assert settings.database_url not in response.text
        assert client.get("/index.html").status_code == 200


def test_deployment_validation(setup):
    with pytest.raises(ValueError, match="FRONTEND_MODE"):
        replace(setup["settings"], frontend_mode="typo")
    with pytest.raises(ValueError, match="FRONTEND_MODE=shared"):
        replace(setup["settings"], environment="production", serve_frontend=True, frontend_mode="mock")


def test_bootstrap_first_admin_does_not_overwrite_accounts(empty_engine):
    from backend.database import make_session_factory
    from backend.tests.conftest import migrate

    migrate(empty_engine)
    factory = make_session_factory(empty_engine)
    profile = RegisterIn(email="first@example.com", display_name="First Admin", password="Test-Password-123!")
    with factory() as db, db.begin():
        admin = bootstrap_admin(db, profile)
        assert admin.role == "admin" and admin.password_hash.startswith("$argon2id$")
    with factory() as db, db.begin():
        with pytest.raises(RuntimeError, match="already exists"):
            bootstrap_admin(db, profile)
    with factory() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 1
