# S05 real PostgreSQL acceptance

Date: 2026-10-21 (Australia/Perth). S05 local database foundation verified; authentication, assignment service, vectors, and cloud were not yet complete.

## Environment

Docker Engine 29.7.2/Linux; PostgreSQL 17.11 (Debian17.11-1.pgdg12+2). Image:

```text
pgvector/pgvector:pg17@sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d
```

Compose project supportopsai, container supportopsai-db-1, volume supportopsai_postgres_data, loopback127.0.0.1:5432. Generated a random password in ignored .env without printing it. Before setup no matching container/volume/port listener existed; public tables=0 before migration.

## Actual commands/results

| Directory | Operation | Result |
|---|---|---|
| Root | docker compose up -d --wait --wait-timeout 60 db | Pinned image pulled; healthy |
| Root | psql SHOW server_version; public table count |17.11;0 tables before migration |
| backend | check_database.py before migration | Exit1/database_unavailable_or_unmigrated |
| backend | uv run --locked alembic upgrade head | Empty DB -> four business tables + revision table |
| backend | uv run --locked alembic current |0001_ticket_foundation (head) |
| backend | check_database.py after migration | Exit0/database_ready |
| backend | seed.py twice | Both successful, no duplicates |
| backend | uv run --locked python ../scripts/test_backend.py -q | **19 passed in 1.07s,0 skipped** |

Actual seed counts: users5, tickets1, messages0, events1; all accounts disabled. No real user data imported.

Fourteen integration cases passed: model/migration agreement, isolated downgrade/upgrade, stale revision readiness, repeat seed preserving edits, eight invalid ticket-state constraints, author FK, and event-failure rollback of assignee/version. Five unit/health tests also passed. Dedicated supportops_test random schemas were cleaned; afterward random test schemas=0 and public test tables=0. Development data was not cleared.

## HTTP and persistence

Port8000 belonged to another process and was not stopped. Temporary API used127.0.0.1:8765.

1. Running DB: GET /ready ->200/database_ready.
2. docker compose stop db: /health ->200, /ready ->503.
3. Finally restored DB with docker compose up -d --wait --wait-timeout 45 db.
4. /ready ->200/database_ready again.
5. Stable primary-key-ordered JSONB fingerprints of four business tables plus revision table matched before/after:249bf379f3f396a8180d3541c48ccef8.

The fingerprint establishes this stop/start comparison only, not backup/security integrity. Persistence is not a backup/restore drill. Stop the temporary API afterward; leave the development DB healthy. docker compose stop db preserves its volume.

scripts/test_backend.py loads local .env, creates a missing localhost-only _test DB, and passes its URL via child environment without printing credentials. Existing databases remain; only owned random schemas are cleaned.

No vector extension, authentication/roles, assignment service, or audit at this stage. A01-A12 belonged to S06-S08. Remote CI, backup/recovery, cloud, and Docker behavior after Windows reboot remained unverified.
