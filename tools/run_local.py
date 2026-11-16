"""Serve the existing database and frontend together; never initialize data implicitly."""

import argparse
import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Use separate backend/luxstay-demo.db")
    parser.add_argument("--init-demo", action="store_true", help="Initialize that NEW dev database once")
    parser.add_argument("--check", action="store_true", help="Read-only database check, then exit")
    args = parser.parse_args()
    os.chdir(ROOT)

    from backend.config import Settings
    from backend.database import make_engine, make_session_factory
    from sqlalchemy import text
    from sqlalchemy.engine import make_url

    settings = Settings.from_env()
    if settings.environment != "development":
        parser.error("This launcher is development-only; production is configured separately.")
    if args.demo or args.init_demo:
        os.environ["DATABASE_URL"] = "sqlite:///" + (ROOT / "backend/luxstay-demo.db").as_posix()
        settings = Settings.from_env()
    url = make_url(settings.database_url)
    if url.get_backend_name() == "sqlite":
        if not url.database or url.database == ":memory:":
            parser.error("Use a persistent SQLite file, not an in-memory database.")
        database = Path(url.database).resolve()
        print(f"SQLite file: {database}", flush=True)
        if args.init_demo:
            if database.exists():
                parser.error("Demo file already exists; refusing to migrate, seed or overwrite it.")
        elif not database.is_file():
            parser.error(
                "Database does not exist. Restore/configure your existing DATABASE_URL. "
                "For a SEPARATE new dev database only, run --init-demo, then --demo."
            )
    engine = make_engine(settings.database_url)
    try:
        if args.init_demo:
            from alembic import command
            from alembic.config import Config
            from backend.seed import seed_database

            password = getpass.getpass("NEW demo accounts password (8-128 characters, hidden): ")
            if not 8 <= len(password) <= 128:
                parser.error("Password must contain 8-128 characters.")
            config = Config(str(ROOT / "backend/alembic.ini"))
            with engine.begin() as connection:
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
            with make_session_factory(engine)() as db:
                result = seed_database(db, password, "development")
            print(result)
            print("Created separate demo database. Start with: python tools/run_local.py --demo")
            return
        with engine.connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            if revision != "0007_booking_holds":
                parser.error("Database schema is outdated. Back up and review migrations; not applied automatically.")
            counts = {
                table: connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
                for table in ("users", "homestays", "rooms", "bookings")
            }
            print(f"Schema: {revision}; rows: {counts}", flush=True)
            if not counts["homestays"]:
                print("Catalog is empty. No data was seeded; add homestays through the host workflow.")
    except Exception as error:
        # Do not print SQL parameters, database credentials or request bodies.
        parser.exit(1, f"Database check failed ({type(error).__name__}); check DATABASE_URL/schema.\n")
    finally:
        engine.dispose()
    if args.check:
        return
    os.environ["SERVE_FRONTEND"] = "true"
    os.environ["FRONTEND_MODE"] = "shared"
    print("Open http://127.0.0.1:8000/index.html?mode=api (Live Server is not needed)", flush=True)
    import uvicorn

    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
