# S07: Ticket writes and pagination

S07 passed 155 tests; [historical evidence](evidence/2026-10-21-ticket-workflow.md). S08 adds [transactional audit](audit.md), reaching 173 tests. M2 business pages remain planned.

## Endpoints

Bearer tokens are required. Writes require Idempotency-Key: 1-128 ASCII letters/digits or `._:-`. All writes except creation require strict positive expected_version. Unknown fields, boolean/string versions, invalid nulls, and PostgreSQL null characters return 422.

| Method/path | Input | Success |
|---|---|---|
| POST /api/tickets | title,body | 201 TicketSummary; open/normal/version1; server chooses requester |
| GET /api/tickets | status,priority,assignee_id,q,limit,cursor | 200 items,next_cursor within current scope |
| PATCH /api/tickets/{id} | expected_version and permitted fields | 200 TicketSummary |
| POST /api/tickets/{id}/messages | expected_version,visibility,body | 201 message,ticket_version |

TicketSummary has basic fields, without messages/events. Detail response isolation follows S06. Store timestamptz and return timezone-aware timestamps.

## Fields and transitions

- Requesters create tickets, post public messages on their writable tickets, and reopen their resolved tickets to in_progress.
- Agents access only current assignments and post public/internal messages or allowed status changes.
- Only managers edit assignee_id, priority, or archived. Closed, non-archived tickets allow manager metadata edits but not ordinary messages.
- Assignment requires a currently active agent; missing/inactive/wrong-role targets return 422. Explicit null clears assignment, except in_progress/waiting_customer.
- Assignment does not change status implicitly. Only closed tickets may archive; archived tickets allow a standalone unarchive action only, before further changes.

| Transition | Roles | Additional rule |
|---|---|---|
| open -> in_progress | Current agent/manager | Active assignee; manager may assign atomically |
| in_progress -> waiting_customer | Current agent/manager | Required public_reply |
| waiting_customer -> in_progress | Current agent/manager | Active current assignee |
| in_progress/waiting_customer -> resolved | Current agent/manager | Required public resolution reply |
| resolved -> in_progress | Owning requester/current agent/manager | Public reason; retain active assignee; no simultaneous reassignment |
| resolved -> closed | Manager | Manual close |
| closed -> open | Manager | Public reason; clear assignee; no simultaneous assignment |

reason is only for reopening; public_reply only for entering waiting_customer/resolved. Other conversation uses messages. Ordinary replies do not automatically change state. No actual change returns 422/no_changes; illegal transition returns 409. See [states](state-transitions.md).

## Transactions, concurrency, idempotency

1. Reread/share-lock the actor and check current active/role.
2. Lock the ticket within current visibility before cache lookup. Former agents cannot replay old cached responses after reassignment.
3. Unique scope: actor_id,resource_id,operation,key. SHA-256 hashes canonical payload JSON. Creation uses a fixed collection UUID; other operations use the ticket ID.
4. Matching retries return the original status/body; different payloads return 409. Replayed content is historical, not the latest resource; clients should refetch/invalidate.
5. Check expected_version and issue conditional UPDATE with version+1/updated_at. Share-lock target assignees to coordinate with disabling.
6. Business writes, one aggregate TicketEvent/version, success audit, and idempotency response commit together. Sort events by version. Replays add no event/audit/version.

Concurrent duplicate creates wait on the unique index. A committed winner supplies the cached response; a rolled-back claim permits execution. Failures consume no successful result/key. Records currently have no expiry; retry transient database failures with the original key.

TicketEvent is business history, distinct from audit_events. Services never commit; the API prepares its response and commits once.

## Lists and search

- Keyset created_at DESC,id DESC; default 20/max 100.
- Signed cursors bind current identity, role, filters, and limit, using a separate audience/purpose. Expired/tampered/mismatched cursors return 422/invalid_cursor and cannot authenticate.
- q searches original title/body only, not internal notes. Percent/underscore are literal; input is parameterized.
- Every page reapplies object scope. There is no cross-request snapshot/total count. New inserts do not shift already-consumed positions; changed fields/permissions require refetching.

## Repeat checks

```powershell
# backend; PostgreSQL running
uv run --locked python ../scripts/test_backend.py -q
# API running separately
uv run --locked python ../scripts/check_tickets.py --base-url http://127.0.0.1:8765
```

The HTTP script retains one labeled synthetic closed/archived ticket per run. It is not a read-only health check and never prints credentials.
