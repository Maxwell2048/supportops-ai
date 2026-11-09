"""Explicitly seed and activate synthetic accounts in the local Compose stack."""
import os

from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from supportops.config import load_settings
from supportops.db import check_readiness, make_engine
from supportops.demo_accounts import activate_demo_accounts
from supportops.seed import seed


def main():
    settings = load_settings()
    if not settings.database_url or make_url(settings.database_url).host != 'db':
        raise SystemExit('This command is restricted to the local Compose database service')
    password = os.getenv('DEMO_PASSWORD')
    if not password:
        raise SystemExit('Set DEMO_PASSWORD in the calling environment')
    engine = make_engine(settings.database_url)
    try:
        if not check_readiness(engine)[0] or not settings.jwt_secret:
            raise SystemExit('Database migrations and authentication configuration are required')
        with Session(engine) as session, session.begin():
            seed(session)
            changed = activate_demo_accounts(session, password)
        print(f'Activated {changed} synthetic accounts; existing account states were preserved')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
