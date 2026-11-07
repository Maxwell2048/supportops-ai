"""Run the single local mock analysis worker."""
import argparse
import time

from sqlalchemy.orm import Session

from supportops.config import load_settings
from supportops.db import make_engine
from supportops.generation import MockGeneration
from supportops.jobs import claim_job, execute_job


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = load_settings()
    if not settings.database_url:
        raise SystemExit("DATABASE_URL is required")
    engine = make_engine(settings.database_url)
    provider = MockGeneration()
    try:
        while True:
            with Session(engine) as session, session.begin():
                claimed = claim_job(session)
            if claimed:
                execute_job(engine, *claimed, provider)
            if args.once:
                break
            if not claimed:
                time.sleep(2)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
