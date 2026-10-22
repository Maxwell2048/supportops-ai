"""Run backend tests with an isolated local PostgreSQL test database.

From backend: uv run --locked python ../scripts/test_backend.py -q
The local password is read from .env and never passed on the command line.
"""

import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from supportops.config import load_settings


def main() -> int:
    database_url = load_settings().database_url
    if not database_url:
        raise SystemExit("Configure local .env before running database tests")
    url = make_url(database_url)
    if url.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("This helper creates a local test database only")
    if not url.database or url.database.endswith("_test"):
        raise SystemExit("Configure the development database; the helper adds _test")
    test_name = url.database + "_test"
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", test_name):
        raise SystemExit("Unsupported local test database name")
    admin = create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT",
        hide_parameters=True, connect_args={"connect_timeout": 3},
    )
    try:
        with admin.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": test_name},
            ).scalar()
            if not exists:
                identifier = connection.dialect.identifier_preparer.quote(test_name)
                connection.execute(text(f"CREATE DATABASE {identifier}"))
                print(f"Created dedicated local test database: {test_name}", flush=True)
    finally:
        admin.dispose()
    environment = os.environ.copy()
    environment["TEST_DATABASE_URL"] = url.set(database=test_name).render_as_string(hide_password=False)
    arguments = sys.argv[1:] or ["-q"]
    return subprocess.run(
        [sys.executable, "-m", "pytest", *arguments],
        cwd=ROOT / "backend", env=environment, check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
