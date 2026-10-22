"""Run from backend: uv run --locked python ../scripts/seed.py."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from supportops.seed import main


if __name__ == "__main__":
    main()
