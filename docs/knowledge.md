# S13: Immutable knowledge and publication

Date: 2026-10-27 (Australia/Perth). [Execution evidence](evidence/2026-10-27-knowledge-versioning.md); [ADR0009](adr/0009-immutable-knowledge-and-current-scope.md).

## Identity and workflow

A knowledge article is a logical topic. Each save inserts a new immutable version with its own UUID, number, title, body, support/management scope, provenance, author/time and SHA256 content hash. Draft content is immutable too: editing a draft means creating another version. There is no version PATCH/DELETE API. The hash covers canonical JSON of normalized title/body/scope/source_kind/source_reference/license_note; it is a content fingerprint, not proof of source trust or license validity.

The article stores a revision counter, latest version number, one nullable published-version pointer, archive flag and timestamps. New version numbers advance only on draft creation; article revision advances on draft creation, publication and archive. One pointer enforces at most one current publication without rewriting old snapshots. A composite foreign key prevents pointing to a different article's version.

Manager article detail/list uses the latest saved version, which may be a draft while an older version remains published. Detail also returns the actual published_version_id and revision. Agent article detail/list uses only the current available support publication and omits the internal revision counter. A version response reports draft if never published, published if it is current/active, and archived if previously published but superseded or withdrawn. Historical archived status alone does not establish current eligibility.

Publishing replaces the pointer and clears article archive. Managers may deliberately publish a historical version as a rollback or republish an archived current version. Archiving requires the specified version to be the active publication. Creating a new draft never publishes or unarchives anything. There is no automatic publication or model-driven workflow.

## Current authorization and old references

| Reader/resource | Result |
|---|---|
| Requester, any supported knowledge operation |403; no knowledge UI/API access |
| Agent, active current support publication | Read/list allowed |
| Agent, never-published draft or management version |404 |
| Agent, historical support version previously published | Read by version ID only while the article remains active and its current publication is also support |
| Agent, old support version after current scope becomes management |404, including historical references |
| Agent, any version after article archive |404 |
| Agent, version directory or audit history |403; only explicit authorized version reads |
| Manager | Read all drafts/history; create/publish/archive and query history |

This deliberately preserves the established support/management scopes. It does not introduce requester-public knowledge. Every request loads current active identity/role. Writes re-read/lock the current manager before checking idempotency, and serialize on the article row. Historical reference reads check both the historical version's scope and the current publication's scope in the authorization SQL. A stable version UUID cannot bypass newly restricted access. Restoring a support publication may restore access to previously published support history; management snapshots stay hidden.

active_versions in knowledge_service.py defines the current-publication eligibility relation for S14 retrieval. Historical read permission is broader than current retrieval eligibility: superseded versions remain traceable for authorized history but are not current search candidates. Search, chunks, vectors and suggestions are not implemented in S13.

## Endpoints and recovery

All endpoints require an existing bearer session. Writes require an Idempotency-Key and return a normal redacted request ID.

| Method/path | Contract |
|---|---|
| POST /api/knowledge/articles | title1..200, body1..50000, scope=support/management, source_kind=synthetic/licensed, source_reference1..2000, license_note1..1000. New topic omits article_id/expected_revision; new version requires both. Returns201 article + version |
| POST /api/knowledge/articles/{id}/publish | version_id and strict positive expected_revision; returns200 |
| POST /api/knowledge/articles/{id}/archive | current published version_id and expected_revision; returns200 |
| GET /api/knowledge/articles | Authorized summaries; manager latest snapshots or agent current support publications |
| GET /api/knowledge/articles/{id} | Manager latest saved snapshot/revision/publication pointer or agent current authorized publication |
| GET /api/knowledge/versions/{id} | Exact immutable snapshot with current access checks |
| GET /api/knowledge/articles/{id}/versions | Manager-only version summaries |
| GET /api/knowledge/articles/{id}/events | Manager-only transactional publication audit |

Lists accept limit1..100(default20) and signed cursors. Article/version directories sort UUID ascending, not by title or recency. Events sort article revision ascending. Cursors bind current account, role, page size, operation and article where applicable; tampering/reuse in another scope returns422. Each page rechecks current visibility. There is no total count or snapshot guarantee under concurrent changes, and there is no keyword search endpoint yet.

Stale revision returns409; invalid/empty/null/extra fields return422. Missing versions or cross-article version IDs return404. Already-active publication returns422/no_changes. Wrong/already-archived target returns409. Current role authorization precedes cached write replay. The generic idempotency store separates knowledge operations from tickets. Successful retries return the original receipt without a new revision/event. An old publication receipt does not reactivate that historical publication; use a fresh current read to establish current state. Changed payload with the same key returns409.

Article/version/event/idempotency updates share one transaction, committed by the route only after preparing the response. A knowledge audit insertion failure rolls back all associated writes and allows retrying the failed key. Knowledge events have real article/version FKs, one event per article revision, actor role/result, request UUID and allowlisted hash/scope/pointer/archive metadata. They exclude free text, titles and license notes. The existing ticket audit table and /api/audit-events remain ticket-only; knowledge audit has its own explicit history endpoint.

## Migration, immutability and seed data

0004_knowledge_versions adds three tables, FK/check/unique constraints and PostgreSQL triggers rejecting UPDATE/DELETE/TRUNCATE of snapshots and knowledge audit. Article publication pointers remain mutable through the service. Trigger protection is for ordinary DML, not privileged schema administration; migrations/backup/recovery remain operational controls. No historical migrations were edited. Readiness now expects0004.

From backend, after the normal local database/auth setup:

```powershell
uv run --locked alembic upgrade head
uv run --locked python ../scripts/seed_knowledge.py
# Explicit synthetic demo publication only after reviewing the bundled fixtures:
uv run --locked python ../scripts/seed_knowledge.py --publish
```

The importer requires the existing activated synthetic manager. Four original English fixtures are in data/knowledge/synthetic-v1.json: three support and one management. It imports drafts by default. Stable operation keys make repeat imports safe; they do not overwrite edits or unarchive historical content. The explicit --publish option uses the original draft revision and will conflict rather than overwrite an intervening change. Reusing a successful publication key returns only its original receipt. The S13 development run imported drafts twice; it did not publish them.

Provenance fields are mandatory for all content. Licensed-source references are stored as literal text; the server does not fetch URLs or certify licensing. Only bundled synthetic data was used in verification. The target20-30 articles and evaluation labels remain later work.

## Verification boundary

Real PostgreSQL tests cover metadata parity, empty/old migration upgrades, DML immutability, FK safety, current authorization, visibility changes, concurrency, idempotency and audit rollback. Real HTTP tests cover publication/history restrictions through the normal Vite/API path. Ticket component/E2E regressions remain in place. There is no knowledge management frontend, search/vector/model execution, citation extraction, cloud deployment or verified remote CI in this stage.
