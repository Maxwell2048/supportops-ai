# Foundation verification

Date: 2026-10-16 (Australia/Perth). Scope: repository scaffold, not business/cloud acceptance. This English translation preserves the historical results.

## Environment/dependencies

Windows/PowerShell; Git 2.55.0.windows.5; Python 3.14.7; uv 0.12.10; Node 22.23.2; npm 10.9.8; Docker CLI 29.7.2. Available versions were verified through PyPI JSON/npm registries before lock generation.

| Component | Version |
|---|---|
| API | FastAPI 0.143.2, Uvicorn 0.54.0 |
| Tests | pytest 9.1.1, httpx 0.28.1 |
| UI | React/React DOM 19.3.1 |
| Build | Vite 8.3.4, TypeScript 7.0.2, React plugin 6.1.2 |

Transitive dependencies: backend/uv.lock and frontend/package-lock.json.

## Executed successfully

| Directory | Command/check | Result |
|---|---|---|
| Root | git init -b main | Local repository; no remote at that time |
| backend | uv lock; uv sync --locked | 24 resolved packages including project;23 dependencies installed |
| backend | uv run --locked pytest | 1 passed in 0.29s, no warnings |
| backend | uv run --locked uvicorn supportops.main:app --app-dir src --host 127.0.0.1 --port 8000 | Real process started |
| backend | GET /health | 200, status=ok, service=supportops-api |
| backend | GET /ready | 503/database_integration_pending, expected then |
| backend | GET /openapi.json | 200; health/ready only |
| frontend | npm ci | Clean install; npm reported0 known vulnerabilities for that run |
| frontend | npm run build | TypeScript/Vite passed,15 modules |
| Root | docker compose --env-file .env.example config --quiet | Parsing passed; no engine connection |

Initial Starlette TestClient use produced an httpx deprecation warning. Switching to httpx ASGITransport passed again. The checks established liveness without falsely claiming dependency readiness.

## Unverified at that stage

Docker info could not reach the Docker Desktop Linux engine named pipe. Database/image digest/extensions awaited S05. No database, migrations, authentication, tickets, worker, AI, or business tests existed. The frontend had build verification only, without browser/component/E2E checks. GitHub Actions was configuration only, without database CI/branch protection. No remote, commits, Azure resources, or publication existed. The temporary API was stopped.

Next then: complete M0 consistency review, then S05. These results concern the scaffold only.
