"""Import only the bundled, versioned synthetic knowledge fixtures.

New drafts are the default. --publish is an explicit synthetic-demo publication.
Caller/service checks require the existing activated synthetic manager.
"""
import argparse
import json
from pathlib import Path

from sqlalchemy.orm import Session

from supportops.config import load_settings
from supportops.db import check_readiness, make_engine
from supportops.knowledge_schemas import KnowledgeChange, KnowledgeCreate
from supportops.knowledge_service import change_publication, create_draft
from supportops.seed import synthetic_id

FIXTURES = Path(__file__).resolve().parents[3] / "data" / "knowledge" / "synthetic-v1.json"


def seed_knowledge(session, *, publish=False):
    results = []
    records = json.loads(FIXTURES.read_text(encoding="utf-8"))
    if len({row["key"] for row in records}) != len(records):
        raise ValueError("Synthetic fixture keys must be unique")
    for row in records:
        key = "synthetic-knowledge-v1:" + row["key"]
        payload = KnowledgeCreate(**{name: value for name, value in row.items() if name != "key"})
        if payload.source_kind != "synthetic":
            raise ValueError("This importer accepts bundled synthetic content only")
        result = create_draft(session, synthetic_id("manager"), payload, key)
        if publish:
            result = change_publication(session, synthetic_id("manager"), result.body["id"],
                KnowledgeChange(version_id=result.body["version"]["id"], expected_revision=result.body["revision"]), key + ":publish")
        results.append(result.body)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    settings = load_settings()
    if not settings.database_url:
        raise SystemExit("Configure the local database first")
    engine = make_engine(settings.database_url)
    try:
        ready, reason = check_readiness(engine)
        if not ready:
            raise SystemExit(f"Cannot import synthetic knowledge: {reason}")
        with Session(engine) as session, session.begin():
            rows = seed_knowledge(session, publish=args.publish)
        print(f"Processed {len(rows)} bundled synthetic knowledge fixtures; existing idempotent results reused.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
