# S08: Transactional audit and request tracing

Date: 2026-10-22 (Australia/Perth). Migration: 0003_audit_events. [Execution evidence](evidence/2026-10-22-audit-verification.md).

S13 adds a separate FK-backed immutable knowledge audit stream in0004, queried at /api/knowledge/articles/{id}/events. The ticket-only table/endpoint described here remains intact; see [knowledge transaction policy](knowledge.md). This avoids inserting article IDs into a ticket resource FK.

## Why this follows ticket writes

S07 makes ticket changes correct. S08 identifies who changed what through which request. Establishing the transaction/tracing contract before business pages gives them reliable outcomes, and future human AI review can reuse it.

Ticket events are authorized staff-facing business history; audit_events are manager-facing operation evidence; JSON request logs diagnose success, rejection, and runtime failure.

## Success audit

- One success audit per effective create/PATCH/message operation and ticket version. Multi-field PATCH plus public reply remains one aggregate audit.
- Ticket, message, event, audit, and idempotency writes share one Session/transaction. Commit only after all writes succeed; Session exit rolls failures back. Audit CHECK failure leaves no partial writes or successful idempotency result; retrying the original key remains possible.
- actor_id comes from current server identity; actor_role is the execution-time role snapshot. resource_id references the ticket. Actions: ticket.created/assigned/updated/message_added; result: success.
- Server UUID request_id matches the first executing HTTP response. Direct service callers may set session.info.request_id; otherwise a generated UUID does not pretend to reference a real HTTP request.
- Successful idempotency replays create no event/audit/version. Each replay has its own request log/ID, while the original audit remains linked to the original write. Query by resource to find that record.
- changes allowlist: status,assignee_id,priority,archived,message_id,visibility. Never copy reopening reasons, titles/bodies, messages, email, passwords, tokens, or idempotency keys.
- 0003 does not backfill invented historical request IDs. Earlier ticket events may have no audit counterpart; only effective writes through the upgraded API create new audit records.

## Manager query

GET /api/audit-events requires an active authenticated manager. Agents/requesters receive403; invalid sessions401. No client create/update/delete audit endpoint exists.

Filters: resource_type (ticket only), resource_id,actor_id,request_id,action. limit defaults 20, range 1-100. Response: items,next_cursor. Items include actor/role, resource, action/result, request ID, version, minimal changes, UTC time.

Order: created_at DESC,id DESC; UUID breaks timestamp ties. Expiring signed cursors bind manager identity, all filters, and limit, with an audience separate from ticket cursors/login tokens. Restart when identity/filter/limit changes. No total count or cross-request snapshot guarantee.

## Failure tracing

Each completed HTTP request emits one JSON line: event, UTC timestamp, request_id, method, route template, status, duration_ms, authenticated actor_id/role, safe error_code. Unmatched paths use unmatched. Do not log raw URLs/queries, headers, bodies, IPs, SQL parameters, exception text, or tracebacks. Incoming X-Request-ID cannot replace the server UUID.

Business errors, validation422, database503, and unexpected500 use the same ID in error body, response header, and logs. Database/unexpected exceptions return generic prompts. Dependency Sessions unwind before unexpected failure responses.

Authentication failures, denials, conflicts, validation failures, and database failures produce request logs, not success audit. Logs are independent of rolled-back transactions, currently process stderr only. Persistent collection, retention, and cloud alerts remain unimplemented. Crashes/client cancellation do not guarantee completion logs.

Disable Uvicorn's raw access log to avoid a second logger recording query strings:

```powershell
# backend; use 8765 when 8000 is occupied
uv run --locked uvicorn supportops.main:app --app-dir src --host 127.0.0.1 --port 8765 --no-proxy-headers --no-access-log
```

The development database account has DDL privileges; audit is not tamper-proof against administrators. Read-only audit roles, least privilege, persistent collection, and Azure tracing are later delivery. No compliance certification is claimed.

## Checks

```powershell
# backend; database running
uv run --locked python ../scripts/test_backend.py -q
# Start API in another terminal first
uv run --locked python ../scripts/check_tickets.py --base-url http://127.0.0.1:8765
```

The HTTP script retains a labeled [S08 smoke] synthetic ticket, ending closed/archived. It writes data and prints no credentials. Audit fault injection uses real CHECK constraints in isolated tests; production APIs expose no fault-injection route.
