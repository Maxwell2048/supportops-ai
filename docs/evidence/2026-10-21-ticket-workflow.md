# S07 ticket-write acceptance

Date: 2026-10-21 (Australia/Perth). Local API scope verified; S08 audit and M2 frontend were not yet complete.

## Implementation

Create/list/filter/search/signed keyset pagination; PATCH assignment/priority/status/archive; public replies/internal notes. Migration0002 adds persistent idempotency without changing0001. Services share-lock/reread actors, validate role/object scope, lock tickets/assignees, and update conditionally on expected_version. Business writes, one aggregate event/version, and successful idempotency responses commit together; authorization precedes replay. Input allowlists/server authors/strict versions/null-character rejection.

## Automated results

From backend: `uv run --locked python ../scripts/test_backend.py -q`:

```text
155 passed in 7.16s
```

Zero skips on real PostgreSQL 17.11. No new dependencies; uv lock --check passed,38 packages including project.

Coverage: prior S05/S06; three-role writes; all distinct manager status pairs; required public replies/reopen reasons; active assignees; archive boundaries; injected author/owner fields; stale409; idempotency content/identity/resource/operation binding. Deliberately broken event FK rolled create/assignment/message/idempotency back; same-key retry succeeded.

Lists cover equal timestamps, inserts during paging without duplicates, filters/identity/role/limit binding, tampering, cursors not authentication, literal percent/underscore search, and internal-note search isolation.

Independent connections verified:

- Same-version edits: one success, one409.
- Same-key create: same content returns one persisted result; different content yields201/409.
- Duplicate concurrent reply: one message/version increment.
- Target disabling holds a real row lock; Event synchronizes assignment, which waits then observes committed inactive and returns422.
- Another connection disables/downgrades a cached actor; service rereads and returns401/403.

Functional tests isolate requests with savepoints inside an outer rollback. Concurrent tests commit within owned random schemas and never share a request Session. Cleanup does not clear development data. Initial equal-timestamp event ordering was nondeterministic by UUID; switching to ticket_version fixed the failing regression.

## Online migration

Before:0001, users5/tickets1/events1; temporary S07 API8765 returned503/database_schema_outdated. alembic upgrade head ->0002_ticket_idempotency, unchanged old counts, idempotency0, ready200. Isolated tests also verified empty/roundtrip/model alignment and old-seed preservation.

## Real HTTP

`uv run --locked python ../scripts/check_tickets.py --base-url http://127.0.0.1:8765` passed:

Requester create/replay -> manager assign -> agent start -> internal note/replay -> waiting+public reply -> requester reply -> resume -> transfer -> resolve -> requester reopen -> resolve -> manager close -> archive.

Evidence ticket9c1006cc-4371-42a0-8a85-684d68647cf0 ended version 13/closed/archived with events1-13. Checks included requester assignment403, other requester404, stale409, internal isolation, former-agent detail/old-key replay404, archived message409, filtered list match.

check_auth then passed five-account login/me/401/403/404. No credential/token output. The HTTP helper retains one labeled synthetic closed/archived ticket per run, deleting no prior records.

## Limits and final aggregates

At that stage audit/manager query/structured logs awaited S08; events were not full audit. A01/A06 audit and A05 client input preservation remained open. No cross-request snapshot, no automatic idempotency expiry, process-local login throttles. Remote CI/cloud unverified; frontend unchanged/not rebuilt. Temporary API stopped; DB stayed running.

Final: users5/tickets2/messages6/events14/idempotency13; incomplete0. Evidence ticket remained closed/archived/version 13. Random test schemas0; .env ignored; Python syntax/local Markdown links/git diff --check passed;8765 closed.
