"""The local launcher must not silently replace or initialize a database."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def launch(database_url, *arguments):
    environment = os.environ.copy()
    environment.update(APP_ENV="development", DATABASE_URL=database_url)
    return subprocess.run(
        [sys.executable, str(ROOT / "tools/run_local.py"), *arguments],
        cwd=ROOT / "frontend",
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_missing_database_is_not_created(tmp_path):
    missing = tmp_path / "missing.db"
    result = launch("sqlite:///" + missing.as_posix(), "--check")
    assert result.returncode != 0
    assert "Database does not exist" in result.stderr
    assert not missing.exists()


def test_existing_database_is_checked_without_reseed(setup):
    if setup["engine"].dialect.name != "sqlite":
        pytest.skip("Byte preservation check applies to SQLite files")
    database = Path(setup["engine"].url.database)
    before = database.read_bytes()
    result = launch(setup["settings"].database_url, "--check")
    assert result.returncode == 0, result.stderr
    assert "0007_booking_holds" in result.stdout
    assert "homestays" in result.stdout
    assert database.read_bytes() == before


def test_unmigrated_database_is_not_migrated(tmp_path):
    import sqlite3

    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE legacy (value TEXT)")
        connection.execute("INSERT INTO legacy VALUES ('preserve')")
    before = database.read_bytes()
    result = launch("sqlite:///" + database.as_posix(), "--check")
    assert result.returncode != 0
    assert "Database check failed" in result.stderr
    assert database.read_bytes() == before


def test_demo_initialization_is_separate_and_refuses_existing_file(tmp_path, monkeypatch):
    import secrets

    from tools import run_local

    (tmp_path / "backend").mkdir()
    (tmp_path / "backend/alembic.ini").write_text(
        "[alembic]\nscript_location = " + (ROOT / "backend/migrations").as_posix() + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run_local, "ROOT", tmp_path)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("JWT_SECRET", secrets.token_urlsafe(48))
    original = tmp_path / "existing.db"
    original.write_bytes(b"Existing database must not be touched")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + original.as_posix())
    monkeypatch.setattr(sys, "argv", ["run_local.py", "--init-demo"])
    monkeypatch.setattr("getpass.getpass", lambda _: secrets.token_urlsafe(24))
    run_local.main()
    demo = tmp_path / "backend/luxstay-demo.db"
    assert demo.is_file()
    assert original.read_bytes() == b"Existing database must not be touched"
    before = demo.read_bytes()
    with pytest.raises(SystemExit):
        run_local.main()
    assert demo.read_bytes() == before
