# Local database and migrations

S05 passed 19 tests; [historical evidence](evidence/2026-10-21-postgresql-verification.md). S08 passed 173 tests and requires 0003_audit_events; see [audit](audit.md).

## Prepare PostgreSQL

Use Docker Desktop's Linux engine. Run from the repository root without overwriting an existing .env. The local Docker startup issue was recovered on 2026-10-21. For sailor-ingest.sock failures, run `pwsh -NoProfile -File scripts/start-docker.ps1` to start through Explorer; see [recovery evidence](evidence/2026-10-21-docker-recovery.md).

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# On first setup, replace POSTGRES_PASSWORD in the local .env before starting.
docker compose up -d db
docker compose ps
```

The image uses a verified OCI digest and loopback binding, with a named volume. Compose currently runs only the database. POSTGRES_* initializes credentials on an empty volume; editing .env later does not change existing database passwords.

API/Alembic explicitly load root .env; existing process variables take precedence. DATABASE_URL can override POSTGRES_* and must use postgresql+psycopg. Never publish DSNs or credentials. The local initialization account is not evidence of cloud least privilege.

## Migrate and inspect

From backend:

```powershell
uv sync --locked
uv run --locked alembic upgrade head
uv run --locked alembic current
uv run --locked python ../scripts/check_database.py
uv run --locked python ../scripts/seed.py
```

Readiness checks connectivity and the exact schema revision; missing configuration, connection failure, or stale revision returns 503. Startup does not create tables automatically.

Minimal seed: five fictional accounts, one ticket, one creation event. Stable UUIDs make repeats safe without resetting passwords/active/roles. New accounts default disabled; S06 explicitly activated local demo accounts separately. Approximately 100 tickets and 20-30 knowledge articles remain future targets. Existing local history is preserved when seed wording changes.

## Real database tests

Use a dedicated database whose name ends in _test and random per-module schemas. Only each owned schema is removed; public development tables are never cleared.

```powershell
# backend directory
uv run --locked python ../scripts/test_backend.py -q
```

The helper reads existing .env, creates a missing localhost supportops_test database, and passes its URL through the child environment without printing credentials. S08 result: 173 passed. For manual setup, create the test database once from the root:

```powershell
docker compose exec db createdb -U supportops supportops_test
```

Adjust the username if POSTGRES_USER differs. Then, from backend:

```powershell
# Replace the placeholder locally. Do not commit a real URL; URL-encode its password.
$env:TEST_DATABASE_URL = 'postgresql+psycopg://supportops:<URL-encoded-local-password>@127.0.0.1:5432/supportops_test'
uv run --locked pytest -m integration -v
Remove-Item Env:TEST_DATABASE_URL
```

Tests execute historical migrations, model comparison, roundtrips, stale readiness, constraints, repeatable seeding, authorization, concurrency, and rollback. Without TEST_DATABASE_URL, integration tests explicitly skip. An unreachable configured database fails rather than skipping. PostgreSQL CI is configured; remote execution is not yet verified.

## Stop and evolve

```powershell
# Repository root; preserve the data volume.
docker compose stop db
```

A downgrade is not backup recovery. Prefer forward migrations, assess compatibility/backups first, and keep downgrade experiments inside isolated test schemas. Image availability does not prove pgvector extension/retrieval functionality; choose model/dimension in S14.
