"""Run the bundled synthetic knowledge importer without installing the API package."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))

from supportops.seed_knowledge import main

if __name__ == "__main__":
    main()
