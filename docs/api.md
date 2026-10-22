# API contract (S02 baseline)

Implemented: login/me, ticket create/list/detail/PATCH/messages/events, manager audit queries, health/readiness. AI, knowledge, and dashboard endpoints remain designs. FastAPI generates current OpenAPI.

## Conventions

- JSON, UUID path IDs, UTC ISO 8601 timestamps; protected endpoints use Bearer JWTs.
- Business/validation/database errors: `{ "error": { "code": "...", "message": "...", "request_id": "...", "details": {} } }`. X-Request-ID on responses and Cache-Control:no-store on APIs; validation errors never echo request bodies.
- 401 missing/expired session; 403 prohibited role-level feature; 404 missing/invisible object; 409 version/state/idempotency conflict; 422 invalid input. Extra request fields are forbidden.
- Lists use cursor and limit (default 20, maximum 100), ordered created_at DESC,id DESC. Signed cursors represent a position; changing filters restarts pagination. Response: items/next_cursor, without unauthorized totals.
- Writes require positive expected_version except creation, which starts at version 1. Missing version: 422; stale version: 409.
- Important POST/PATCH operations require Idempotency-Key (1-128 ASCII letters/digits or `._:-`). Bind identity, operation, resource, and canonical payload hash. Matching retries return the original successful result; changed payload returns 409. Records do not expire automatically.
- S07 implements ticket/create/PATCH/message idempotency, successes only, authorization before replay. AI job/review writes remain planned.
- Login limits: 10 attempts/email/minute and 30/IP/minute, including successes; 429 with Retry-After:60. Bounded process memory is not shared across replicas/restarts. Do not log passwords, JWTs, or full bodies.

## Endpoints

| Method/path | Main inputs | Response/permission |
|---|---|---|
| POST /api/auth/login | email,password | 200 access_token,token_type,expires_in; invalid credentials 401 |
| GET /api/me | None | 200 current active identity id,email,role |
| GET /api/tickets | status,priority,assignee_id,q,cursor,limit | 200 authorized list; filters cannot broaden visibility |
| POST /api/tickets | title(1-200),body(1-10000) | 201 TicketSummary; requester only |
| GET /api/tickets/{id} | None | 200 ticket + authorized messages; requester excludes internal fields |
| GET /api/tickets/{id}/events | None | 200 events; authorized agent/manager only |
| PATCH /api/tickets/{id} | expected_version,status?,assignee_id?,priority?,archived?,reason?,public_reply? | 200 TicketSummary; field/state permission and actual change required |
| POST /api/tickets/{id}/messages | expected_version,visibility,body(1-10000) | 201 message,ticket_version; object authorization |
| POST /api/tickets/{id}/analysis-jobs | expected_version | Planned: 202 job_id,status; agent/manager |
| GET /api/analysis-jobs/{id} | None | Planned: 200 status/error/authorized suggestion; current ticket scope |
| POST /api/suggestions/{id}/review | expected_version,decision,edited_body? | Planned: 200 review,message_id?,ticket_version; agent/manager |
| GET /api/knowledge/search | q(1-500),mode(keyword/vector),limit(1-20) | Planned: 200 published authorized version chunks |
| POST /api/knowledge/articles | title,body,visibility,article_id? | Planned: 201 draft/version; manager; article_id identifies existing logical article |
| POST /api/knowledge/articles/{id}/publish | version_id | Planned: 200 published version; manager; id is logical article ID |
| POST /api/knowledge/articles/{id}/archive | version_id | Planned: 200 archived version; manager |
| GET /api/dashboard | None | Planned: 200 backlog/category/first_human_response; manager |
| GET /api/audit-events | resource_type=ticket,resource_id,actor_id,request_id,action,cursor,limit | 200 audit page; manager; [details](audit.md) |
| GET /health | None | 200 process liveness; public |
| GET /ready | None | 200 ready / 503 missing config, unreachable DB, or schema mismatch |

Current readiness requires 0003_audit_events and JWT_SECRET. Login passwords accept 1-128 characters; emails are trimmed/lowercased. Default token lifetime: 900 seconds. Reject unknown fields and null characters. See [auth](auth.md) and [ticket behavior](tickets.md).

Priorities: low/normal/high/urgent. Planned suggestion categories: access/billing/bug/how_to/other; suggestions do not automatically modify tickets. Planned decisions: accepted/edited/rejected; edited requires nonempty edited_body, other decisions forbid it. The server chooses requester_id, author_id, reviewer_id, created_at, and role.

PATCH and public_reply commit atomically; waiting_customer/resolved requires public_reply. Reopening reason becomes a public message. Use messages for ordinary conversation. expected_version is a strict positive integer. Explicit null assignee_id clears assignment; status/priority/archived reject null. Search covers original title/body only. Signed list cursors bind identity/role/filters/limit and cannot authenticate a session.
