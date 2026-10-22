"""From backend: uv run --locked python ../scripts/activate_demo_accounts.py."""

import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from supportops.config import load_settings
from supportops.db import check_readiness, make_engine
from supportops.demo_accounts import activate_demo_accounts
from supportops.security import require_auth_config


def main():
    settings = load_settings()
    require_auth_config(settings)
    if not settings.database_url or make_url(settings.database_url).host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("This activation script is for local synthetic accounts only")
    password = os.getenv("DEMO_PASSWORD")
    if not password:
        raise SystemExit("Set local DEMO_PASSWORD (12-128 characters); do not pass passwords as CLI arguments")
    engine = make_engine(settings.database_url)
    try:
        if not check_readiness(engine)[0]:
            raise SystemExit("Migrate and seed the local database first")
        with Session(engine) as session, session.begin():
            changed = activate_demo_accounts(session, password)
        print(f"Activated {changed} synthetic accounts; credentials not displayed; existing passwords preserved")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
