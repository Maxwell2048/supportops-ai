# S13 execution: Knowledge versions, publication and scopes

Date: 2026-10-27 (Australia/Perth). Historical S05-S12 results remain in their original evidence.

## Implemented

0004 migration/models for logical articles, immutable content/provenance snapshots and FK-backed knowledge audit; manager draft/publication/archive APIs; authorized article/exact-version/history lists; current scope checks for historical references; signed bounded pagination; atomic idempotency/audit; four synthetic fixtures with draft-first importer. [Behavior](../knowledge.md); [ADR0009](../adr/0009-immutable-knowledge-and-current-scope.md).

## Actual checks

Docker helper reported Engine29.7.2 ready; the existing PostgreSQL service reached healthy. Python3.14.7, Node22.23.2, pinned dependencies; no dependency versions or lockfiles changed.

- Initial migration/model parity/old-data tests:17 passed. This included empty roundtrip and upgrading0001/0002/0003 to head.
- First knowledge-specific run:41 passed,1 failed. The failed TRUNCATE test expected a trigger IntegrityError, but PostgreSQL FK preflight rejected that statement first with NotSupportedError. The test was changed to TRUNCATE CASCADE only inside its isolated test schema and now asserts SQLSTATE23514 to prove the immutable trigger fired. The schema/data protection was not disabled.
- Corrected knowledge/concurrency run:46 passed, including independent-connection duplicate creation and competing draft/publication writes. Adding repeatable seed and manager-history paging brought knowledge-specific coverage to48 tests, plus one extra previous-revision migration case.
- Full backend run before the final history-list assertion:225 passed/zero skips,9.57s. The final complete run is recorded below.
- frontend npm ci:110 installed/111 audited, zero vulnerabilities reported; build passed74 modules,141ms Vite build. Existing tests:17 API,11 query/mutation,6 writes,12 rendered components all passed. Test-source type checks passed, including the new HTTP scenario.
- npm run test:e2e: **12 passed in17.8s**, no automatic retries. The existing10 ticket desktop/narrow scenarios passed plus one real knowledge HTTP scenario in each project. The API scenario uses actual authentication, Vite proxy, FastAPI and PostgreSQL; it does not intercept knowledge authorization responses.

## Knowledge assertions

New drafts are manager-owned, normalized, provenance-complete and hash-stable; duplicate keys reuse one article/version/audit result. Requesters receive403, agents cannot mutate/publish or read drafts/management history, and absent sessions receive401. Current role/active state is checked before idempotent replay.

Publishing support v1 exposes only that current version to agents. An unpublished management v2 does not replace it or reveal a draft counter. Publishing management v2 denies old support v1, not only the new restricted text. Publishing support v3 permits authorized history of previously published support v1, while management v2 stays hidden. Archiving denies all agent history. Managers retain exact original body/hash; explicit republishing can restore an old immutable snapshot. Replaying an old publication key does not undo a newer archive.

PostgreSQL rejects snapshot/audit UPDATE, DELETE and TRUNCATE, and cross-article publication pointers. Same revision cannot publish two versions or append two competing drafts; independent connections yield one success/one409 with a single corresponding revision/audit. Audit insertion faults roll back article/content/idempotency, and the failed key retries successfully. Cursor tampering, account/role/page-size/article changes are rejected; manager history and current-scope article pages are bounded. Four bundled fixtures import as drafts, explicitly publish three agent-readable/one management version in the test, repeat without duplication and do not unarchive on reimport.

The real HTTP scenario performed seven effective knowledge changes and read exactly seven revision-ordered audit rows. It verified old content/hash through supersession and denial after scope/archive changes, requester403 and receipt replay without a new publication. This is API execution in both projects, not a new knowledge UI test.

## Local development migration and data preservation

The actual development database upgraded0003_audit_events ->0004_knowledge_versions. Before/after comparisons of existing rows used canonical hashes in memory, excluded password_hash and emitted no record bodies or credentials. Existing counts stayed:users5, tickets3, ticket_messages12, ticket_events27, idempotency_records26, audit_events13. No historical ticket rows, identity roles/active states or audit rows changed.

The four bundled knowledge fixtures were then imported twice as drafts. Both calls returned identical results; no duplicate versions or automatic publications were added. Readiness returned database_ready. The explicit --publish demo command was tested only against disposable schemas, not run on the development data.

## Final results and limits

Final backend total: **226 passed, zero skips**,9.66s, including metadata parity and manager version history pagination. Both idempotency and audit failures are tested through real PostgreSQL; no database fixture skips count as acceptance. Final cleanup confirms zero owned browser schemas and no5174/8766 listeners. Language, Python syntax, Markdown links, secret-value absence and Git whitespace checks run before publication; the supplied Maxwell identity is used for the English stage commit.

No knowledge frontend, keyword/vector retrieval, embeddings, AI generation/citation validation, cloud execution or remote CI result is claimed. Normal DML immutability is not privileged-database tamper resistance. Only four synthetic fixtures exist;20-30 articles and evaluation labels remain targets. Development history was preserved, including any pre-translation synthetic records; repository content remains English. Next: S14 authorized keyword baseline and persistent retrieval representation.
