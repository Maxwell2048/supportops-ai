# S08 audit and tracing acceptance

Date: 2026-10-22 (Australia/Perth). See [audit](../audit.md) and [ADR0005](../adr/0005-transactional-audit-and-request-tracing.md). Historical results are preserved in this English translation.

## Delivery

Migration/model0003, same-transaction ticket success audit, manager filters/pages, server request-ID correlation, redacted JSON request logs, generic unexpected500. New real CHECK-failure/logging tests extend concurrency/migration coverage. No dependency changes; uv lock checks38 packages.

## Executed commands

```powershell
# Root
pwsh -NoProfile -File scripts/start-docker.ps1
docker compose up -d --wait --wait-timeout 60 db
# backend
uv run --locked python ../scripts/test_backend.py -q
uv lock --check
uv run --locked alembic upgrade head
# backend, separate temporary API terminal
uv run --locked uvicorn supportops.main:app --app-dir src --host 127.0.0.1 --port 8765 --no-proxy-headers --no-access-log
# backend, another terminal
uv run --locked python ../scripts/check_tickets.py --base-url http://127.0.0.1:8765
# frontend
npm ci
npm run build
```

- Recovery helper returned Engine 29.7.2; existing supportopsai-db-1 healthy on PostgreSQL 17.11 volume, without data/credential reset.
- Final: **173 passed in 7.45s,0 skipped**. Dedicated supportops_test random schemas execute real Alembic and clean after modules; no SQLite/create_all substitute.
- uv lock --check passed,38 packages.
- npm ci:24 packages added,0 vulnerabilities reported then; tsc/Vite 8.3.4 build passed. Static-scaffold verification, not business-page/E2E acceptance.
- Initial logging test:1 failed/169 passed because an unconfigured DB dependency returned503 before the expected422. A test-only DB-free validation route correctly isolated logging. Then 170 passed; previous-revision coverage 171; unexpected rollback/inactive manager coverage 173. No skips hid failures.

## Migration

Real development DB0002->0003 preserved users5/tickets2/messages6/events14/idempotency13; new audit0. No fabricated historical request IDs. Tests also covered empty upgrade/roundtrip,0001/0002 seed preservation, model comparison, and stale readiness.

Real post-upgrade GET /ready returned200/ready/database_ready. Pre-upgrade HTTP inspection was blocked by a sandbox socket restriction, so this run does not claim a real pre-upgrade503; automated database tests cover the rule. Approved local network execution subsequently worked.

## Real HTTP and tracing

Retained synthetic ticket `29790f2c-f720-4639-b35b-ecc0013b53ed`, labeled [S08 smoke]. Workflow: creation/replay, assignment, internal note/replay, cross-user404, unauthorized403, stale409, public replies, transfer, resolution, reopen, close/archive.

- Final version 13, closed, archived=true. Events1-13 and exactly13 success audits; failures/retries added none.
- Requester/agent audit403; manager200; resource query13 rows, creation-request query1 row.
- Creation request `b6722801-1750-4d41-821a-4879925273a2` matched response header, audit, and log.
- Conflict request `264d080d-d24e-45df-956a-ff825548577d` matched error body/header and actual JSON log: PATCH /api/tickets/{ticket_id},409/version_conflict,6.95ms. No raw URL/query/body/credentials.
- Logs use route templates; audit excludes note body/reopen reason. [JSONL excerpt](2026-10-22-request-traces.jsonl) preserves actual fields with terminal wrapping/control codes removed.

After HTTP: users5/tickets3/messages12/events27/idempotency26/audit13/incomplete0. Earlier data remained; additions were synthetic acceptance records. Temporary API PID 40668 stopped normally;8765 closed; original8000 untouched; DB stayed running.

## Critical assertions

- Corrupt pending audit result to trigger real PostgreSQL CHECK: 503 with complete ticket/message/event/audit/idempotency rollback; same-key retry succeeds after fault removal.
- Unexpected RuntimeError: generic 500 without exception text, full rollback, successful retry.
- Independent concurrent edits have one version winner; duplicate create/message keys produce one success audit.
- Managers only; invalid token/inactive manager401, downgraded role403. Client IDs cannot replace server UUID.
- Equal-time UUID pagination has no duplicate; tampering/changed limit/other manager/cross-interface cursors rejected; cursor cannot authenticate.
- No free text in audit, or exception/header/body/query/path-parameter text in request logs.

## Limits at acceptance time

At S08 acceptance there was no remote, author config, or first commit; [message](../commit-notes/S08.txt) was only prepared. Publication happened afterward: the publication record added in the following documentation commit. No remote CI/Azure/AI/persistent-log/admin-tamper/UI/E2E acceptance. Next: S09 typed API/login/list/details. M1 S05-S08 locally verified.
