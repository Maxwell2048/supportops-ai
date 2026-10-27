# ADR0009: Immutable snapshots, a publication pointer and current historical authorization

Date: 2026-10-27. Status: accepted for S13.

## Context

Future retrieval/citations need stable source identities. Editing a published row would change what an old citation means. Conversely, retaining immutable text must not preserve access after an article becomes management-only or is withdrawn. Existing permissions prohibit requester knowledge access and distinguish support/management; ticket audit uses a ticket-specific resource FK and cannot safely hold article IDs.

## Decision

Keep logical articles separate from immutable version rows. Every draft save creates a UUID/number/hash/provenance snapshot. The article owns one current publication pointer and a separate aggregate revision for optimistic concurrency. A composite FK binds the pointer to the same article. Derived draft/published/archived states replace the earlier planned partial-unique published-status index: one pointer supplies the single-publication invariant without modifying historical rows.

Protect snapshots and publication audit from UPDATE/DELETE/TRUNCATE using PostgreSQL statement triggers. Record knowledge audit in its own FK-backed append-only stream, atomically with article/version/idempotency updates. Keep the existing ticket audit schema/contract intact. Use the existing generic idempotency store with distinct knowledge operation names and current manager checks before replay.

Requester access stays forbidden. Agents read active support publications; explicitly requested historical versions also require previous publication, historical support scope, a currently active article and a current support publication. Managers can inspect all history. Restricting current scope or archiving invalidates historical agent access; restoring support publication may restore support history. Current retrieval eligibility remains only the active pointer, not all historically readable versions.

Publication can explicitly restore an old snapshot for controlled rollback. An idempotent replay is a historical receipt, not a state transition. Draft imports never auto-publish. Provenance is mandatory; stored references are not fetched, and license validity remains a human review responsibility.

## Consequences

Old citation UUIDs keep their exact text/hash while current authorization can deny access. New versions cost storage even for small edits; scope corrections create new snapshots. Manager detail shows the latest draft alongside the active publication pointer, while agent views exclude unpublished metadata. PostgreSQL-specific triggers add migration/restore considerations and do not protect against privileged DDL. Keyword/vector retrieval and UI management remain later work.

References: [PostgreSQL17 triggers](https://www.postgresql.org/docs/17/sql-createtrigger.html), [SQLAlchemy composite and cyclic foreign keys](https://docs.sqlalchemy.org/en/21/core/constraints.html).
