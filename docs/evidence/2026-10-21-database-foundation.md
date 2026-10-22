# Initial database foundation verification

Date: 2026-10-21 (Australia/Perth). Scope: initial S05 implementation/assignment acceptance preparation, not completed database acceptance.

Later update: Docker recovery and real PostgreSQL subsequently passed all 19 tests; see [real database evidence](2026-10-21-postgresql-verification.md). Results below preserve the earlier blocked stage.

## Delivered

- A01-A12 assignment criteria and the first learning guide.
- User/ticket/message/event models with FKs, state/visibility/version/archive constraints and initial indexes.
- Immutable first Alembic migration; space-containing repository paths supported.
- Root .env/process configuration without password output; connectivity/revision readiness with safe driver errors.
- Repeatable minimal synthetic seed: five disabled accounts, one ticket/event, preserving existing changes.
- Dedicated _test database/random-schema integration tests and PostgreSQL CI service configuration.

PyPI-verified/pinned SQLAlchemy 2.1.5, Alembic 1.20.0, psycopg[binary] 3.3.6, python-dotenv 1.2.4; uv.lock updated.

`docker buildx imagetools inspect pgvector/pgvector:pg17` succeeded and returned the OCI index digest pinned in Compose/CI:

```text
sha256:ac08538c6f8b9904c33c8224c5e5706dbe760aca29db1d096972b4052c22a75d
```

Only the remote manifest was verified then, not image execution or vector extension.

## Execution results

| Check | Result |
|---|---|
| backend: uv lock / uv sync --locked |32 packages resolved including project |
| backend: uv run --locked pytest -q | **5 passed,14 skipped in 0.63s** |
| backend: uv lock --check | Passed |
| backend: uv run --locked python -m compileall -q src migrations ../scripts | Passed |
| backend: temporary offline URL, alembic upgrade head --sql | Four business tables + alembic_version SQL generated; no connection |
| Root: docker compose --env-file .env.example config --quiet | Parsing passed only |
| Root: git diff --check | No whitespace errors; line-ending normalization warnings only |

Five passing checks covered missing-config health/readiness, hidden password repr, two unsupported-driver rejections, and safe readiness errors. Fourteen integration cases skipped for missing usable TEST_DATABASE_URL: migrations/models, roundtrip, stale readiness, seed repetition, eight invalid states, author FK, and event-failure rollback. None counted as actual database verification.

Initial offline migration failed because Alembic split prepend_sys_path at the directory's space. Adding path_separator=os fixed generation. A sandbox async health test stalled; the same checks passed in the approved local execution environment.

## Docker blocker

Startup reported Starting but the Linux engine pipe did not appear. Read-only process/log inspection found:

```text
initializing Ingest server ... sailor-ingest.sock:
The file cannot be accessed by the system.
```

After confirming the backend stopped, a single endpoint backup/move was attempted but failed. No successful endpoint modification, Docker reset, volume deletion, or virtualization setting change occurred. At that moment no project DB container or local .env existed.

## Remaining then

Recover Docker; run real container/empty migration/repeated seed/checks; execute all isolated database tests and HTTP readiness/rollback; fix actual compatibility failures before marking verified. S06/S07 followed later, without unauthenticated business endpoints. Frontend unchanged/not rebuilt; no remote CI/cloud resources.
