import os
import secrets
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from backend.config import Settings
from backend.database import make_engine, make_session_factory
from backend.main import create_app
from backend.models import Homestay, Room, User
from backend.security import hash_password, issue_token

ROOT = Path(__file__).resolve().parents[2]
PASSWORD = "Test-Password-123!"


def pytest_configure(config):
    if config.option.basetemp is None:
        parent = ROOT / "backend/.test-tmp"
        parent.mkdir(exist_ok=True)
        config.option.basetemp = str(parent / ("run-" + secrets.token_hex(8)))


def migrate(engine, revision="head"):
    config = Config(str(ROOT / "backend/alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


@pytest.fixture(scope="session")
def password_hash():
    return hash_password(PASSWORD)


@pytest.fixture(params=["sqlite"] + (["postgresql"] if os.getenv("TEST_POSTGRES_URL") else []))
def empty_engine(request, tmp_path):
    admin_engine = None
    schema = None
    if request.param == "postgresql":
        base_url = make_url(os.environ["TEST_POSTGRES_URL"])
        if not base_url.database or not base_url.database.endswith("_test"):
            pytest.fail("TEST_POSTGRES_URL must reference a dedicated database ending in _test")
        admin_engine = make_engine(base_url.render_as_string(hide_password=False))
        schema = "luxstay_test_" + secrets.token_hex(12)
        with admin_engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        url = base_url.set(query={**base_url.query, "options": "-csearch_path=" + schema}).render_as_string(
            hide_password=False
        )
    else:
        url = "sqlite:///" + (tmp_path / "test.db").as_posix()
    engine = make_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()
        if admin_engine:
            assert schema.startswith("luxstay_test_") and len(schema) == 37
            with admin_engine.begin() as connection:
                connection.execute(DropSchema(schema, cascade=True))
            admin_engine.dispose()


@pytest.fixture
def setup(empty_engine, tmp_path, password_hash):
    engine = empty_engine
    url = engine.url.render_as_string(hide_password=False)
    settings = Settings(
        database_url=url,
        jwt_secret=secrets.token_urlsafe(48),
        environment="test",
        upload_dir=tmp_path / "uploads",
        serve_frontend=False,
        auth_rate_limit=100,
    )
    migrate(engine)
    factory = make_session_factory(engine)
    with factory() as db:
        for uid, role in [(1, "user"), (2, "user"), (3, "host"), (4, "host"), (5, "admin")]:
            db.add(
                User(
                    id=uid,
                    email=f"account{uid}@example.com",
                    display_name=f"Account {uid}",
                    role=role,
                    phone="0912345678",
                    password_hash=password_hash,
                )
            )
        db.flush()
        for hid, owner in [(1, 3), (2, 4)]:
            db.add(
                Homestay(
                    id=hid,
                    host_id=owner,
                    name=f"Homestay {hid}",
                    description="A real test homestay description",
                    address="Da Lat, Lam Dong",
                    city="Da Lat",
                    location="Da Lat, Lam Dong",
                    amenities=["Wi-fi", "Pool"],
                    images=["img/placeholder.svg"],
                )
            )
        db.flush()
        for rid, hid, key, price, capacity, inventory in [
            (1, 1, "room-one", 100000, 2, 2),
            (2, 1, "room-two", 150000, 4, 1),
            (3, 2, "other-room", 200000, 2, 1),
        ]:
            db.add(
                Room(
                    id=rid,
                    homestay_id=hid,
                    key=key,
                    name=f"Room {rid}",
                    description="Room description",
                    price_per_night=price,
                    capacity=capacity,
                    inventory=inventory,
                    images=["img/placeholder.svg"],
                )
            )
        db.flush()
        if engine.dialect.name == "postgresql":
            for table in ["users", "homestays", "rooms"]:
                db.execute(
                    text(
                        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), (SELECT MAX(id) FROM {table}))"
                    )
                )
        db.commit()
        tokens = {}
        for uid in range(1, 6):
            tokens[uid] = issue_token(db, db.get(User, uid), settings)
        db.commit()
    app = create_app(settings, engine)
    try:
        with TestClient(app) as client:
            yield {
                "client": client,
                "engine": engine,
                "factory": factory,
                "settings": settings,
                "tokens": tokens,
                "app": app,
            }
    finally:
        engine.dispose()


@pytest.fixture
def client(setup):
    return setup["client"]


@pytest.fixture
def headers(setup):
    return lambda uid=1: {"Authorization": "Bearer " + setup["tokens"][uid]}


@pytest.fixture
def booking_payload():
    from datetime import timedelta

    from backend.booking_service import business_today

    checkin = business_today() + timedelta(days=10)
    return {
        "homestayId": 1,
        "checkIn": checkin.isoformat(),
        "checkOut": (checkin + timedelta(days=2)).isoformat(),
        "adults": 2,
        "children": 0,
        "rooms": [{"key": "room-one", "qty": 1}],
        "guestName": "Test Guest",
        "guestEmail": "guest@example.com",
    }
