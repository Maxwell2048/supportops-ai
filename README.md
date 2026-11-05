# SupportOps AI

An AI-assisted ticket and knowledge collaboration platform for a fictional software support team. This portfolio project demonstrates full-stack development, authorization, data consistency, AI evaluation, and eventual Azure delivery.

**Current stage: M3 S14 locally verified: authorized keyword and vector retrieval over immutable knowledge versions. Next: S15 generation provider boundaries.**

The original requirements are preserved in an English translation of the [project brief](docs/planning/project-brief.md). Its planning-only statements describe the archived starting point. The current local repository is `D:\SupportOps AI`.

## Available now

- Git repository on `main`: [Maxwell2048/supportops-ai](https://github.com/Maxwell2048/supportops-ai). Cloud resources and deployment remain planned.
- FastAPI `/health` for process liveness and `/ready` for database connectivity, migration version, and authentication configuration; unavailable dependencies return 503.
- React/TypeScript/Vite login, role-scoped ticket list/details, public/internal conversation, staff activity, and loading/empty/error/success views; see [frontend guide](docs/frontend.md).
- Exact dependency versions, `uv.lock`, and `package-lock.json`; TanStack React Query 5.105.0 provides per-session cache lifecycle and current-access revalidation.
- GitHub Actions configuration for PostgreSQL backend tests, frontend build, protocol/component tests and isolated browser regression. The workflow passed on the [browser synchronization fix](docs/evidence/2026-10-27-remote-ci.md).
- PostgreSQL 17.11 development container, image digest and loopback port pinned; persistence across stop/start verified.
- Four foundational business tables plus idempotency and audit tables, Alembic migrations, synthetic seed data, and real database integration tests.
- Email/password login, short-lived JWTs, current identity, and server-authorized ticket details/events. Requester responses exclude internal messages and events.
- Five explicitly activated synthetic demo accounts; credentials exist only in the ignored local `.env`. No public registration or role-editing API.
- Ticket creation, authorized lists/filters/pagination, assignment, replies, status/archive changes, version conflicts, transactional events, persistent idempotency, manager audit queries, and redacted JSON request logs.
- Role-scoped business forms, a manager-only active-agent directory, retained conflict drafts, duplicate-submit guards and same-request recovery after uncertain write results; see [form policy](docs/forms.md).
- Repeatable Vitest/Testing Library component tests and Playwright three-role workflows in desktop/narrow viewports against an isolated real PostgreSQL API; see [testing guide](docs/testing.md).
- Immutable knowledge snapshots with provenance/hashes, manager draft/publication/archive APIs, support/management scopes, transactional knowledge audit and four draft-first synthetic fixtures; see [knowledge guide](docs/knowledge.md). See also [authorized keyword and vector retrieval](docs/retrieval.md).
- M0 permission, state, data model, API, and data policy drafts; S01-S27 milestone checklist.

## Run locally

Verified environment: Windows, Python 3.14.7, uv 0.12.10, Node 22.23.2, npm 10.9.8. The liveness scaffold can run without a database; business APIs require configuration and migrations.

Complete [database setup](docs/database.md) and [local authentication setup](docs/auth.md), then run from the repository root in PowerShell:

```powershell
Set-Location backend
uv sync --locked
uv run --locked uvicorn supportops.main:app --app-dir src --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log
```

API documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). A 503 readiness response is expected when the database, migration, or JWT secret is unavailable. Stop with Ctrl+C. Local acceptance checks used 8765; set the matching frontend proxy when changing the API port.

Start the frontend in another terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open the address printed by Vite, normally [http://127.0.0.1:5173](http://127.0.0.1:5173). The development proxy forwards `/api`, `/health`, and `/ready` to port 8000 by default. For an API on 8765, set `$env:SUPPORTOPS_API_TARGET = 'http://127.0.0.1:8765'` before npm run dev. Tokens stay in memory; refreshing the page requires login. Stop Vite before npm ci on Windows to release its native binding.

## Verification

Run each command from its specified directory:

```powershell
# backend/
uv run --locked python ../scripts/test_backend.py -q

# frontend/
npm ci
npm run build
npm run test:api
npm run test:query
npm run test:writes
npm run test:types
npm run test:components
npx playwright install chromium
npm run test:e2e
```

The S08 acceptance run passed **173 backend tests with zero skips**; see [audit evidence](docs/evidence/2026-10-22-audit-verification.md). Frontend clean installation and production build passed. The English conversion has its own [verification record](docs/evidence/2026-10-22-english-repository.md). The test helper loads local configuration and prepares a dedicated test database. Running pytest without `TEST_DATABASE_URL` explicitly skips integration tests; skips do not count as database verification. S09 separately passed 173 backend tests, 17 API-client tests, clean install/build, and real browser role/session/error checks; see [frontend evidence](docs/evidence/2026-10-27-frontend-foundation.md). S10 additionally passed 10 query tests, clean install/build, and real multi-page/filter/cache-revalidation browser checks: [S10 evidence](docs/evidence/2026-10-27-query-cache.md). S10 deferred component/E2E regression to S12; the later S12 execution is recorded separately below.

## Database and migrations

S11 passed **177 backend tests with zero skips and 34 frontend tests**, plus clean installation/build and manual browser checks: [S11 evidence](docs/evidence/2026-10-27-ticket-forms.md). S12 newly passed **177 backend, 46 client/component and 10 E2E tests**, test-source type checking, clean installation and production build: [S12 evidence](docs/evidence/2026-10-27-frontend-regression.md). Drafts remain page/session memory only. Broad browser/accessibility coverage remains unverified.

S13 newly passed **226 backend tests with zero skips, 46 client/component tests and 12 E2E cases**, plus clean installation/type checks/build. Development migration0003->0004 preserved existing rows, and four synthetic knowledge drafts imported twice without duplication: [S13 evidence](docs/evidence/2026-10-27-knowledge-versioning.md).

The root `.env.example` is the local configuration template. The current machine already has a generated `.env`; do not overwrite it or casually change the existing database password.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# On first setup, edit POSTGRES_PASSWORD before starting the database.
docker compose up -d db
```

On 2026-10-21, Docker recovery, empty-database migration, repeatable seeding, real integration tests, and stop/start persistence were verified; see [PostgreSQL evidence](docs/evidence/2026-10-21-postgresql-verification.md). See [database operations](docs/database.md) for migrations and testing. S14 passed 262 backend tests, 46 client/component tests, and 12 E2E cases, plus a separate real Ollama and pgvector run. See [S14 evidence](docs/evidence/2026-10-27-retrieval.md). Full application Compose belongs to S22.

If starting Docker from the desktop agent encounters the socket access issue again:

```powershell
pwsh -NoProfile -File scripts/start-docker.ps1
```

The helper checks the engine first and starts Docker Desktop through Windows Explorer only if needed.

## Milestones

| Milestone | Goal | Status |
|---|---|---|
| M0 | Permissions, states, ER model, API, data modes | Drafted; consistency review pending |
| M1 | Database, authentication, three-role ticket API, audit | S05-S08 locally verified |
| M2 | React business pages, caching, component tests, E2E | S09-S12 locally verified; Chromium workflow passed on the CI fix |
| M3 | Knowledge versions, retrieval, AI jobs, citations, human review | S13-S14 locally verified; S15-S19 planned |
| M4 | SQL/AI evaluation, Compose, recovery, complete CI | Planned |
| M5 | Azure, IaC, observability, release rollback, portfolio evidence | Planned |

Tasks, dependencies, acceptance, and next steps live in [progress](docs/progress.md). MLflow, PySpark, and Databricks are optional extensions after the main track.

## Design and operating guides

- [Architecture and directories](docs/architecture.md)
- [Permissions and unauthorized-access examples](docs/permissions.md)
- [State transitions](docs/state-transitions.md)
- [Data model and ER diagram](docs/data-model.md)
- [API contract](docs/api.md)
- [Synthetic data and mock/local modes](data/README.md)
- [Assignment acceptance criteria](docs/acceptance/ticket-assignment.md)
- [First engineering exercise](docs/learning/01-data-and-assignment.md)
- [Authentication configuration](docs/auth.md)
- [Ticket transactions, idempotency, pagination](docs/tickets.md)
- [Transactional audit and tracing](docs/audit.md)
- [Frontend sessions, pages, proxy, and browser fixtures](docs/frontend.md)
- [Query cache, filters, and pagination policy](docs/query-cache.md)
- [Business forms and safe write recovery](docs/forms.md)
- [Component tests and isolated browser regression](docs/testing.md)
- [Knowledge versions, publication and history permissions](docs/knowledge.md)
- [GitHub setup and commit policy](docs/git-workflow.md)
- [Foundation decision](docs/adr/0001-foundation-and-scope.md)

All repository content, code comments, commit messages, and GitHub-facing communication use English. Conversation with the project owner may use Chinese. Use only synthetic or explicitly licensed data. AI drafts require human review and cannot send replies or close tickets automatically. Implemented does not mean verified; this project does not claim production employment, customer scale, or unmeasured performance gains.
