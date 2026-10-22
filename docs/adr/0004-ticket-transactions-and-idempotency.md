# ADR 0004: Ticket transactions, versions, and idempotency

Date: 2026-10-21. Status: accepted; locally verified.

- 0002 adds idempotency_records without changing executed 0001 or recreating business tables. At S07, readiness requires 0002; older databases return 503.
- Reread/share-lock the actor, lock the authorized ticket, then check the target assignee, within one transaction. Ordinary account UPDATE coordinates with share locks; future account management must avoid reversed multi-resource lock ordering.
- Version-conditional UPDATE plus ticket row locks prevent stale pages from overwriting newer changes. State, event, message, and idempotency writes commit together.
- Identity/resource/operation/key uniquely scope idempotency. INSERT ON CONFLICT handles concurrency. Cache successes only; authorize before replay.
- Creation, PATCH, and messages return explicit DTOs without internal fields. Replayed responses are historical operation snapshots; clients must fetch current state.
- One aggregate TicketEvent per version, sorted by version rather than timestamp/UUID. S08 adds success audit and failure tracing.
- Signed (created_at,id) cursors bind identity, role, filters, and page size. Do not claim cross-page snapshots or measured performance.
- public_reply supplies a resolution; reopening reason becomes a public message. Managers may edit closed-ticket metadata, but ordinary messages remain prohibited. Archived tickets accept standalone unarchive only.

References: [PostgreSQL row locks](https://www.postgresql.org/docs/17/explicit-locking.html), [Read Committed](https://www.postgresql.org/docs/17/transaction-iso.html), [SQLAlchemy ON CONFLICT](https://docs.sqlalchemy.org/en/21/dialects/postgresql.html#insert-on-conflict-upsert). Independent-connection tests verify these mechanisms here, without extrapolating enterprise-scale performance.

See [ticket evidence](../evidence/2026-10-21-ticket-workflow.md).
