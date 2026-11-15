"""Explicit first-admin bootstrap. Never seeds catalog or upgrades the database."""

import getpass
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import select, text

from .config import Settings
from .database import make_engine, make_session_factory
from .models import User
from .schemas import RegisterIn
from .security import hash_password


def bootstrap_admin(db, profile):
    config = Config(str(Path(__file__).with_name("alembic.ini")))
    head = ScriptDirectory.from_config(config).get_current_head()
    if db.execute(text("SELECT version_num FROM alembic_version")).scalar_one() != head:
        raise RuntimeError("Migrate the database to the current head before bootstrap")
    if db.bind.dialect.name == "postgresql":
        # Serialize concurrent invocations without creating a table or a second auth system.
        db.execute(text("SELECT pg_advisory_xact_lock(762091384)"))
    if db.scalar(select(User.id).where(User.role == "admin").limit(1)) is not None:
        raise RuntimeError("An admin already exists; use the existing administration workflow")
    if db.scalar(select(User.id).where(User.email == str(profile.email))) is not None:
        raise RuntimeError("Email already exists; no account was modified")
    admin = User(
        email=str(profile.email),
        display_name=profile.display_name,
        phone=profile.phone,
        role="admin",
        password_hash=hash_password(profile.password.get_secret_value()),
    )
    db.add(admin)
    db.flush()
    return admin


def main():
    settings = Settings.from_env()
    email = input("Admin email: ").strip()
    name = input("Admin display name: ").strip()
    password = getpass.getpass("Admin password: ")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords do not match; no data changed")
    try:
        profile = RegisterIn(email=email, display_name=name, password=password)
    except ValueError:
        raise SystemExit("Invalid email, name or password; no data changed") from None
    engine = make_engine(settings.database_url)
    try:
        with make_session_factory(engine)() as db, db.begin():
            bootstrap_admin(db, profile)
        print("First admin created. No catalog or demo data was seeded.")
    except Exception:
        # Never print connection strings, SQL parameters or credentials.
        raise SystemExit(
            "Bootstrap refused or database unavailable. Check migration and existing admin."
        ) from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
