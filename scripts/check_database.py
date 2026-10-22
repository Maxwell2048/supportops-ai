"""Read-only diagnostic: run from backend with uv run --locked python ../scripts/check_database.py."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from supportops.config import load_settings
from supportops.db import check_readiness, make_engine


def main():
    url = load_settings().database_url
    engine = make_engine(url) if url else None
    try:
        ready, reason = check_readiness(engine)
        print(reason)
        return 0 if ready else 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
