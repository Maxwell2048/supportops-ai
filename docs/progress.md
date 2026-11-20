# Progress and staged tasks

Updated: 2026-11-20 (Australia/Perth).

States: planned = unimplemented; drafted = design only; implemented = artifacts exist; verified = actual execution evidence. M1 S05-S08, M2 S09-S12 and M3 S13-S14 are locally verified. Generation provider boundaries begin at S15.

## Delivery history

- Repository: [Maxwell2048/supportops-ai](https://github.com/Maxwell2048/supportops-ai), main. Git identity is configured locally as Maxwell using the supplied email, without global changes. Initial publication is documented in [Git evidence](evidence/2026-10-22-git-publication.md).
- Requirements: [archived brief](planning/project-brief.md). Root README describes current state. Permissions, states, ER/API/data policies began as M0 drafts.
- 2026-10-16 foundation: FastAPI health/readiness, static React, locks, CI configuration, database Compose; one backend test, real HTTP/OpenAPI, frontend install/build, and Compose parsing passed. At that stage containers/remote CI were unverified: [evidence](evidence/2026-10-16-foundation.md).
- Initial S05 implementation produced models/migrations/config/readiness/seed/isolated tests and PostgreSQL CI. Only5 tests passed,14 skipped because Docker was unavailable; this was not database acceptance: [record](evidence/2026-10-21-database-foundation.md).
- Docker recovered through Explorer; Engine 29.7.2/hello-world passed with no residual smoke container: [recovery](evidence/2026-10-21-docker-recovery.md).
- S05:19 tests passed with zero skips on real PostgreSQL, empty migration/repeated seed/constraints/rollback/readiness/persistence verified: [evidence](evidence/2026-10-21-postgresql-verification.md).
- S06:73 tests passed, zero skips; hashing, JWT, current role/object reads, internal isolation, rate limits, errors, and five-account real login verified: [evidence](evidence/2026-10-21-auth-verification.md).
- S07:155 tests passed, zero skips; ticket writes/list/filter/pagination/version/events/idempotency verified. Existing-data0001->0002 upgrade and real HTTP workflow finished version 13/closed/archived: [evidence](evidence/2026-10-21-ticket-workflow.md).
- S08 implemented:0003 audit migration, same-transaction success audit, manager filters/pagination, JSON request logs, generic unexpected500. See [audit](audit.md) and [ADR0005](adr/0005-transactional-audit-and-request-tracing.md).
- S08 verified:173 tests passed, zero skips;0002->0003 retained old table counts;13 effective HTTP changes produced 13 audit rows, retries/failures added no success audit. Frontend npm ci/build passed. A01/A06 audit verified; A05 client input retention still M2: [evidence](evidence/2026-10-22-audit-verification.md).
- English repository conversion: owner requested all files, comments, fixtures, UI/API text, and published commit messages in English. Historical evidence retains its original dates/outcomes. See [conversion evidence](evidence/2026-10-22-english-repository.md). The two published commits use reconstructed English snapshots/messages with original author timestamps. A local backup and exact remote lease protect the replacement; old publication hashes remain explicitly labeled legacy identifiers. Conversion regression passed 173 tests with zero skips and the frontend build passed; Git results are independently checked during publication.

- S09 implemented: typed/runtime-validated API client, memory-only login, scoped list/details/conversation/activity, four-state feedback, basic cursors, safe errors/request IDs, and cancellable reads. See [frontend guide](frontend.md) and [ADR0006](adr/0006-frontend-session-and-request-boundaries.md).
- S09 verified on 2026-10-27:173 real-PostgreSQL backend tests and 17 API-client tests passed, clean install/build passed, and actual browser checks covered five accounts, internal/object isolation, empty/loading/error/success, delayed logout/account-switch, expiry, revocation401, and offline502. Temporary schema count 0 after cleanup. See [evidence/screenshots](evidence/2026-10-27-frontend-foundation.md).

- S10 implemented: pinned TanStack Query 5.105.0/lockfile, per-session clients/keys, cancellation and clearing, revalidation/error gating, filters/hash URLs, retained cursor navigation, and common invalidation; custom useRemote removed. See [cache policy](query-cache.md) and [ADR0007](adr/0007-session-query-cache-and-revalidation.md).
- S10 verified:173 real-PostgreSQL backend tests, 17 API tests and 10 query tests passed, clean install/build passed. Browser checks covered 20+5 pagination, detail-return state, 12 filtered results, empty filters, switched/revoked accounts, cached-page revalidation, late reads and failed refresh. See [evidence](evidence/2026-10-27-query-cache.md).

## Main track

- S11 implemented: role/state-scoped create/reply/assignment/status/priority/archive forms, manager-only active-agent directory, exact-payload idempotent retries, retained draft/version review, duplicate guards, mutation401 expiry and unavailable-selection handling. See [form policy](forms.md).
- S11 verified on 2026-10-27:177 real-PostgreSQL tests,17 API/11 query-mutation/6 write tests, clean install/build, real two-session reply/assignment conflicts and preserved drafts, agent/manager workflows, lost committed-response recovery, double clicks, unavailable targets and measured390x844 form/keyboard focus. See [new execution evidence](evidence/2026-10-27-ticket-forms.md). Full component/E2E/browser/accessibility coverage remains S12.
- S12 implemented: pinned Vitest/jsdom/Testing Library/Playwright,12 component regressions, two viewport projects with five whole-system scenarios, test-source type checking, an owned API/schema runner, CI commands and safe report policy. See [testing guide](testing.md) and [ADR0008](adr/0008-component-and-isolated-browser-tests.md).
- S12 verified:177 real-PostgreSQL backend tests,46 client/component tests and10 Chromium E2E cases passed; clean install/type checks/build passed. The final browser run took20.2s, covered1280x800 and390x844 without automatic retries, and removed its owned schema. An intentionally invalid project returned the expected failure and also cleaned up; final schema count0/no test listeners. See [new execution evidence](evidence/2026-10-27-frontend-regression.md). Remote CI/Linux, other browser engines and broad accessibility remain unverified.

- S13 implemented:0004 knowledge articles/immutable versions/append-only audit, current publication pointers, manager writes, current support/management authorization for historical reads, signed bounded lists and four draft-first synthetic fixtures. See [knowledge guide](knowledge.md) and [ADR0009](adr/0009-immutable-knowledge-and-current-scope.md).
- S13 verified:226 real-PostgreSQL backend tests,46 client/component tests and12 real HTTP/browser E2E cases passed; clean install/types/build passed. Development0003->0004 preserved existing data in all six original tables; four draft fixtures imported twice without duplication and readiness passed. Historical scope/archive restrictions, independent-connection concurrency, immutable DML and audit rollback were verified. See [new evidence](evidence/2026-10-27-knowledge-versioning.md). Retrieval, knowledge UI, AI/cloud and remote CI remain unverified.

| ID | Milestone | Deliverable/acceptance | Status | Dependencies |
|---|---|---|---|---|
| S01 | M0 | Roles/stories/cross-user negative cases | Drafted | None |
| S02 | M0 | States, ER, API | Drafted | S01 |
| S03 | M0 | Synthetic seed/modes/source policy | Drafted | S01 |
| S04 | M1 | Scaffold/locks/config/health | Locally verified; remote CI S23 | S02,S03 |
| S05 | M1 | PostgreSQL/Alembic/constraints/empty upgrade/pinned digest | Locally verified | S04 |
| S06 | M1 | Hashing/JWT/role-object checks/tampered-expired tokens | Verified; write auth regressed in S07 | S05 |
| S07 | M1 | Create/assign/reply/transition/409/idempotency/cross-user tests | Locally verified API; UI later | S06 |
| S08 | M1 | Atomic audit/rollback/request IDs | Locally verified; persistent/cloud logs later | S07 |
| S09 | M2 | Typed API/login/list/details/four request states | Locally verified; full component/E2E suite remains S12 | S06,S07 |
| S10 | M2 | TanStack Query/pagination/filters/invalidation/user cleanup | Locally verified; full component/E2E remains S12 | S09 |
| S11 | M2 | Forms/duplicate sends/keyboard/narrow screens | Locally verified; broad component/E2E/accessibility S12 | S10 |
| S12 | M2 | Vitest/RTL/Playwright three-role flows | Locally verified; remote CI passed on the browser synchronization fix | S11 |
| S13 | M3 | Immutable knowledge versions/publication/scopes | Locally verified API/data; retrieval added in S14 | S05,S06 |
| S14 | M3 | Keyword baseline/persistent vectors/model-dimension versions | Locally verified with real Ollama and pgvector | S13 |
| S15 | M3 | Provider/timeouts/schema/error classes | Implemented; simulated provider verified, real inference pending | S14 |
| S16 | M3 | Durable jobs/leases/idempotency/restart recovery | Locally verified with mock worker; real crash and model inference pending | S15 |
| S17 | M3 | Contiguous citation checks/evidence-free refusal | Locally verified with mock provider | S15 |
| S18 | M3 | Human review/atomic public reply/deduplication | Backend and review interface verified with mock provider | S08,S16,S17 |
| S19 | M3 | Authorization/injection/knowledge-change regression | Initial synthetic regressions verified; real-model adversarial evaluation remains | S18 |
| S20 | M4 | Fixed data/environment/EXPLAIN/index experiments | Full-row synthetic query and insert observations verified; broader workloads pending | S07 |
| S21 | M4 | 20/10 split/manual labels/baselines/metrics/limits | Synthetic draft baseline measured; independent review and broader evaluation pending | S14,S17,S19 |
| S22 | M4 | Complete Compose/startup/backup/restore | Local synthetic stack and isolated restore verified; production operations pending | S12,S18 |
| S23 | M4 | Database/migration/frontend/mock CI and branch protection | Implemented: CI runs backend, browser and isolated stack restore checks; remote results are recorded per commit; failure blocking and branch protection unverified | S12,S19,S22 |
| S24 | M5 | Azure/Bicep/identity/secrets/OIDC/cost/cleanup | Deferred at the owner's request for the local delivery | S22,S23 |
| S25 | M5 | Cloud logs/real failure tracing | Planned | S24 |
| S26 | M5 | Release/app rollback/independent data restore | Planned | S25 |
| S27 | M5 | README/ADRs/video/measurements/contribution evidence | Planned | S20,S21,S23,S26 |

## S14 retrieval

- Implemented: deterministic version chunks, transactional representation manifests, manager indexing, current authorization before ranking, keyword search, and exact vector search with pinned local embeddings. See [retrieval](retrieval.md) and [ADR 0010](adr/0010-versioned-retrieval-and-local-embeddings.md).
- Verified: 262 backend tests with zero skips, 46 client/component tests, 12 browser cases, and real 384-dimensional Ollama embeddings persisted in pgvector. The development migration preserved existing rows and draft visibility. See [execution evidence](evidence/2026-10-27-retrieval.md).
- Remote CI: the earlier S13 browser synchronization fix passed both jobs. See [exact-run evidence](evidence/2026-10-27-remote-ci.md). The S14 run is checked independently after publication.

## S15 generation provider boundaries

Implemented the structured contract, mock and local adapters, timeouts and failure categories. Simulated HTTP tests and backend/frontend regressions passed. Real generation inference remains unverified. See [generation](generation.md) and [evidence](evidence/2026-11-05-generation.md). Durable jobs and citation validation follow in S16 and S17.
## Stage evidence template

Artifacts -> actual commands -> results/environment -> unverified limitations -> next step. Failed tests cannot be hidden behind an implemented label. Drafts do not substitute for database/browser acceptance.

Optional D01 MLflow -> D02 PySpark -> D03 Databricks remain planned, after the main track; see brief section 13.

## S16 job execution

Implemented persistent jobs, idempotent API creation, lease fencing and a mock worker. Verified 279 PostgreSQL tests and a separate process reclaiming a simulated expired lease. See [jobs](jobs.md) and [evidence](evidence/2026-11-07-analysis-jobs.md). Citation checks and human review remain S17 and S18.

## S17 citation checks

Implemented authorized keyword retrieval, contiguous quotation validation, current publication rechecks, and fixed no-evidence handoff. Verified 290 backend tests with synthetic data and a mock provider. See [citation policy](citations.md) and [evidence](evidence/2026-11-07-citations.md). Human review follows in S18.

## S18 review backend

Implemented and verified atomic human decisions, retry protection, current ticket and source checks, and evidence-free rejection. See [review](review.md) and [evidence](evidence/2026-11-09-review.md). The review interface remains in progress.

## S18 review workspace

Added staff analysis history, source inspection and human decisions to ticket details. Verified component and desktop/narrow browser coverage with synthetic mocked analysis responses. See [UI evidence](evidence/2026-11-09-review-ui.md). The worker remains mock-only.

## S19 initial security regression

Verified role/object boundaries, changed tickets, untrusted source instructions and HTML-like source rendering with synthetic cases. Real-model injection evaluation remains unverified. See [evidence](evidence/2026-11-09-analysis-security.md).

## Local generation compatibility

A synthetic local model call returned structured output and an authentic quote after a grammar compatibility fix. The model misclassified the sign-in example. The worker remains mock-only. See [local generation evidence](evidence/2026-11-09-local-generation.md).

## S20 initial SQL observation

Executed a 5,000-row temporary synthetic query-plan comparison without changing application indexes. See [experiment evidence](evidence/2026-11-09-sql-experiment.md). Full-workload and repeated observations remain open.

## Knowledge workspace

Added the manager workspace for current drafts, keyword indexing, publication and archive. The complete 22-case browser suite and 17 component tests passed with synthetic fixtures. See [evidence](evidence/2026-11-09-knowledge-ui.md).

## Pinned local generation worker

Added explicit local model selection with digest checks and stored provenance. Synthetic worker checks produced both rejected and valid outputs. The default remains mock. See [evidence](evidence/2026-11-09-pinned-worker.md).

## Local application stack and restore

Built and ran a separate local Compose project with API, frontend and mock worker. Restored a synthetic archive to a new database and matched 15 table fingerprints. See [operations guide](compose.md) and [evidence](evidence/2026-11-09-compose.md).

## Provisional retrieval evaluation

Measured keyword and real local vector retrieval over a 30-case synthetic draft split. Labels lack independent human review and the four-article corpus makes vector Hit@5 non-discriminating. See [evaluation evidence](evidence/2026-11-09-retrieval-evaluation.md).

## Full-row SQL observation

Repeated the ticket query and 1,000-row insert measurements with the real migrated table in an isolated synthetic schema. See [evidence](evidence/2026-11-09-sql-full.md). Broader production-like workload measurement remains open.

## Ticket contact details

Added optional phone capture and authorized staff visibility of requester account email. Verified existing data preservation, role/object restrictions and browser flows. See [evidence](evidence/2026-11-09-ticket-contact.md). Azure deployment is deferred for the local delivery at the owner request.

## Generation source visibility

Implemented explicit provider labels in the review workspace. Verified clean frontend installation, build, type and component checks, plus four actual worker browser cases. See [evidence](evidence/2026-11-09-provider-visibility.md). The labels do not certify output quality.
