# Progress and staged tasks

Updated: 2026-10-22 (Australia/Perth).

States: planned = unimplemented; drafted = design only; implemented = artifacts exist; verified = actual execution evidence. M1 S05-S08 are locally verified. Business frontend remains unimplemented.

## Delivery history

- Repository: [Maxwell2048/supportops-ai](https://github.com/Maxwell2048/supportops-ai), main. The supplied Maxwell identity is configured locally; initial publication is documented in the following commit.
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

## Main track

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
| S09 | M2 | Typed API/login/list/details/four request states | Planned | S06,S07 |
| S10 | M2 | TanStack Query/pagination/filters/invalidation/user cleanup | Planned | S09 |
| S11 | M2 | Forms/duplicate sends/keyboard/narrow screens | Planned | S10 |
| S12 | M2 | Vitest/RTL/Playwright three-role flows | Planned | S11 |
| S13 | M3 | Immutable knowledge versions/publication/scopes | Planned | S05,S06 |
| S14 | M3 | Keyword baseline/persistent vectors/model-dimension versions | Planned | S13 |
| S15 | M3 | Provider/timeouts/schema/error classes | Planned | S14 |
| S16 | M3 | Durable jobs/leases/idempotency/restart recovery | Planned | S15 |
| S17 | M3 | Contiguous citation checks/evidence-free refusal | Planned | S15 |
| S18 | M3 | Human review/atomic public reply/deduplication | Planned | S08,S16,S17 |
| S19 | M3 | Authorization/injection/knowledge-change regression | Planned | S18 |
| S20 | M4 | Fixed data/environment/EXPLAIN/index experiments | Planned | S07 |
| S21 | M4 | 20/10 split/manual labels/baselines/metrics/limits | Planned | S14,S17,S19 |
| S22 | M4 | Complete Compose/startup/backup/restore | Planned | S12,S18 |
| S23 | M4 | Database/migration/frontend/mock CI and branch protection | Planned | S12,S19,S22 |
| S24 | M5 | Azure/Bicep/identity/secrets/OIDC/cost/cleanup | Planned | S22,S23 |
| S25 | M5 | Cloud logs/real failure tracing | Planned | S24 |
| S26 | M5 | Release/app rollback/independent data restore | Planned | S25 |
| S27 | M5 | README/ADRs/video/measurements/contribution evidence | Planned | S20,S21,S23,S26 |

## Next: S09 typed frontend and business pages

1. Prefer scripts/start-docker.ps1 for recurring startup-context issues. Windows-reboot behavior is not verified.
2. S08 has173 passing tests and schema0003; old development data remains. Temporary acceptance API8765 was stopped.
3. Backend assignment/audit criteria are verified; frontend input retention remains M2. Credentials stay ignored.
4. Preserve ticket rules, concurrency/retry behavior, and labeled synthetic acceptance records.
5. Audit success shares business transactions; failures use redacted process logs, without persistence or administrator tamper resistance.
6. S09 adds typed API calls, in-memory session tokens, login/list/details, loading/empty/error/success states, server-driven public/internal visibility, and401/403/404/409/request-ID handling. Hidden buttons never replace authorization.
7. S10 refines Query caching; S11 forms/accessibility; S12 component/E2E verification.
8. Every stage gets a detailed first-person English commit message and evidence. Use the supplied local Git identity; verify remote CI separately from push success.

Auth parameters are fixed in auth.md/ADR0003. Embedding/model choices (S14/S15), worker parameters (S16), and Azure region/pricing/resources/shared throttling (S24) remain open.

## Stage evidence template

Artifacts -> actual commands -> results/environment -> unverified limitations -> next step. Failed tests cannot be hidden behind an implemented label. Drafts do not substitute for database/browser acceptance.

Optional D01 MLflow -> D02 PySpark -> D03 Databricks remain planned, after the main track; see brief section 13.
