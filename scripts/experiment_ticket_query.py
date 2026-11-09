"""Compare a synthetic ticket-list query with and without a temporary index.

Run from backend: uv run --locked python ../scripts/experiment_ticket_query.py
Only a local dedicated test database is accepted. All experiment objects are temporary.
"""
import json
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "src"))
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from supportops.config import load_settings


def main():
    configured = load_settings().database_url
    if not configured:
        raise SystemExit("Local database configuration is required")
    url = make_url(configured)
    if url.host not in {"127.0.0.1", "localhost", "::1"} or not url.database or url.database.endswith("_test"):
        raise SystemExit("Configure a local development database; the experiment uses its dedicated test database")
    engine = create_engine(url.set(database=url.database + "_test"), hide_parameters=True, connect_args={"connect_timeout": 3})
    query = "SELECT id, created_at FROM experiment_tickets WHERE assignee_id = md5('7')::uuid AND status = 'open' ORDER BY created_at DESC, id DESC LIMIT 21"
    explain = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + query
    try:
        with engine.begin() as connection:
            version = connection.scalar(text("SHOW server_version"))
            connection.execute(text("CREATE TEMP TABLE experiment_tickets (id uuid PRIMARY KEY, assignee_id uuid NOT NULL, status text NOT NULL, created_at timestamptz NOT NULL) ON COMMIT DROP"))
            connection.execute(text("INSERT INTO experiment_tickets SELECT md5(n::text)::uuid, md5((n % 20)::text)::uuid, CASE WHEN (n / 20) % 5 = 0 THEN 'open' ELSE 'closed' END, TIMESTAMPTZ '2025-01-01 00:00:00+00' + n * INTERVAL '1 second' FROM generate_series(1, 5000) AS n"))
            connection.execute(text("ANALYZE experiment_tickets"))
            baseline_ids = list(connection.execute(text(query)))
            baseline = connection.scalar(text(explain))[0]
            connection.execute(text("CREATE INDEX experiment_assignee_status_created ON experiment_tickets (assignee_id, status, created_at DESC, id DESC)"))
            connection.execute(text("ANALYZE experiment_tickets"))
            indexed_ids = list(connection.execute(text(query)))
            indexed = connection.scalar(text(explain))[0]
            if baseline_ids != indexed_ids or len(indexed_ids) != 21:
                raise RuntimeError("Indexed and baseline result pages differ")
            print(json.dumps({"postgresql": version, "python": platform.python_version(), "platform": platform.platform(),
                "rows": 5000, "query": query, "matching_page_rows": len(indexed_ids),
                "baseline": baseline, "indexed": indexed}, indent=2))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
