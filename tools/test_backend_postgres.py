"""Run tests on an isolated temporary PostgreSQL cluster, not the existing service.

Run: backend/.venv/Scripts/python tools/test_backend_postgres.py
POSTGRES_BIN may override C:/Program Files/PostgreSQL/17/bin.
"""

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    binaries = Path(os.getenv("POSTGRES_BIN", "C:/Program Files/PostgreSQL/17/bin"))
    if not (binaries / "initdb.exe").exists():
        raise SystemExit("Set POSTGRES_BIN to an installed PostgreSQL bin directory")
    parent = (root / "backend/.test-tmp").resolve()
    parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pg-", dir=parent) as directory:
        work = Path(directory).resolve()
        if work.parent != parent or not work.name.startswith("pg-"):
            raise RuntimeError("Refusing a temporary cluster outside the dedicated test directory")
        cluster = work / "data"
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        result = subprocess.run(
            [
                str(binaries / "initdb.exe"),
                "-D",
                str(cluster),
                "-A",
                "trust",
                "--no-locale",
                "-E",
                "UTF8",
                "-U",
                "luxstay_test",
            ],
            capture_output=True,
            text=True,
            creationflags=flags,
        )
        if result.returncode:
            print(result.stderr)
            raise SystemExit("Could not initialize the isolated test cluster")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        log = work / "postgres.log"
        process = None
        try:
            with log.open("w", encoding="utf-8") as output:
                process = subprocess.Popen(
                    [
                        str(binaries / "postgres.exe"),
                        "-D",
                        str(cluster),
                        "-h",
                        "127.0.0.1",
                        "-p",
                        str(port),
                        "-c",
                        "fsync=off",
                    ],
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    creationflags=flags,
                )
                import psycopg

                for attempt in range(100):
                    try:
                        with psycopg.connect(
                            host="127.0.0.1",
                            port=port,
                            user="luxstay_test",
                            dbname="postgres",
                            connect_timeout=2,
                            autocommit=True,
                        ) as connection:
                            connection.execute("CREATE DATABASE luxstay_test")
                        break
                    except psycopg.OperationalError:
                        if process.poll() is not None:
                            raise RuntimeError("Temporary PostgreSQL process exited; inspect its test log")
                        time.sleep(0.1)
                else:
                    raise RuntimeError("Temporary PostgreSQL did not become ready")
                environment = os.environ.copy()
                environment["TEST_POSTGRES_URL"] = (
                    f"postgresql+psycopg://luxstay_test@127.0.0.1:{port}/luxstay_test"
                )
                print("Running SQLite + isolated PostgreSQL tests", flush=True)
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", "backend/tests", "-q", "--tb=short", *sys.argv[1:]],
                    cwd=root,
                    env=environment,
                )
                return result.returncode
        finally:
            if process is not None:
                subprocess.run(
                    [str(binaries / "pg_ctl.exe"), "-D", str(cluster), "-m", "fast", "-w", "stop"],
                    capture_output=True,
                    creationflags=flags,
                )
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
