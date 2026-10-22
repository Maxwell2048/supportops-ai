# SupportOps AI

> Project kickoff and cross-conversation handoff, 2026-10-16.
>
> **Archived starting state: planning only; development had not started.** Features, architecture, directories, and acceptance targets below were requirements, not completed work. The project name was provisional; no repository or cloud resources had been created in that planning session.
>
> This is the English translation of the archived requirements, requested by the owner on 2026-10-22. It preserves scope and historical context. Current implementation status belongs to the root README and docs/progress.md.

## 1. Instructions for a new conversation

Read this document completely as the project's requirements; do not redesign an unrelated project.

The owner is applying for software/AI application development roles. An explainable, runnable, verifiable personal project should strengthen evidence of React/TypeScript, business APIs, multi-user authorization, PostgreSQL, tests, containers, CI/CD, Azure, and AI evaluation.

At the time of writing only planning existed. Reading the brief did not authorize implementing everything or creating paid resources. Follow explicit user directions. When asked to start, complete M0 and then the smallest M1 business workflow rather than opening every stage simultaneously.

At startup:

1. Inspect the real working directory, existing files, Git state, and applicable AGENTS.md; preserve existing edits.
2. Use an independent project directory, suggested name supportops-ai. Honor the owner's path; otherwise create a separate subdirectory in the authorized workspace and report its absolute path.
3. The original handoff was stored with another project's analysis references, not this project's source root. Do not mix business code into that older project.
4. Verify/pin dependencies and tool versions; do not assume this brief is a runnable scaffold or that runtimes exist.
5. Give short progress updates and finish/verify/record stages. Do not create other chats, publish repositories, or deploy paid resources by default.
6. Do not copy private resumes, reports, databases, or keys from earlier projects. Use synthetic or clearly licensed public data only.
7. Update progress/next steps per stage. Mark completion only when artifacts and real acceptance evidence exist.

Confirmed direction: software/AI application development. The original deliverable was the complete plan/checklist. Later Azure and Spark/Databricks/MLflow discussion is included; data-platform extensions remain optional.

## 2. Product purpose

SupportOps AI is an AI-assisted ticket and knowledge collaboration platform for a fictional software support team.

```text
Requester submits ticket
  -> Manager assigns support agent
  -> Agent requests analysis
  -> Retrieve published, authorized knowledge
  -> Generate a reply draft with citations
  -> Human accepts / edits / rejects
  -> Public reply and status update
  -> Audit, metrics, and failure tracing
```

RAG is one business capability. The central deliverable is complete business software and engineering delivery: authorization, consistency, failure recovery, and human review.

### Relationship to existing portfolio work

| Project | Main evidence |
|---|---|
| Job Application Assistant | Trustworthy generation, citations, personal application workflow |
| GeoMind | Visual modeling, evaluation, team project |
| Finance Planner | Web application foundation |
| SupportOps AI (planned at kickoff) | Multi-user business system, engineering quality, Azure delivery |

Do not describe a personal demo as commercial client experience, enterprise production scale, or years of operations work. Disclose AI assistance and personal contributions accurately.

## 3. Scope and completion levels

- Local MVP: three-role ticket workflow, real PostgreSQL, authorization, knowledge retrieval, human-reviewed AI drafts, core tests, Compose startup.
- Portfolio version: MVP plus Azure demonstration, cloud security, CI/CD, observability, backup/recovery, release rollback, evaluation, and evidence pack.
- Optional data extension: MLflow experiments, PySpark analysis, Databricks workflows, after the main track passes.

Out of scope initially: real customer onboarding, payments, multi-tenancy, mobile app, Kubernetes, Kafka, multi-cloud, automatically sending AI replies, and invoking external business systems. Do not introduce both Redis/Celery and a custom queue.

## 4. Roles and permissions

| Role | Allowed | Prohibited |
|---|---|---|
| requester | Submit tickets; read own tickets/public replies | Other tickets, internal notes, audit, selecting assignees, privilege escalation |
| agent | Handle currently assigned tickets; internal notes; AI analysis/review | Role changes, unauthorized tickets, publishing knowledge |
| manager | Assignment, knowledge publication, global metrics/audit, permitted ticket actions | Bypassing audit, treating unreviewed AI drafts as sent replies |

Single organization; no public administrator registration. Hidden frontend buttons are not authorization. Every API, retrieval, and job read checks role and object scope.

Use established password-hashing and short-lived JWT libraries initially; keep client tokens in memory and reauthenticate on expiry. Enterprise OIDC/refresh tokens are later. Choose and document issuer/audience validation for the actual scheme. Do not invent cryptography.

## 5. Technology choices

| Layer | Choice | Evidence required |
|---|---|---|
| Frontend | React + TypeScript + Vite | Types, component boundaries, forms, accessibility, narrow screens |
| Server state | TanStack Query | Query keys, pagination, invalidation, cleanup on user changes |
| API | Python + FastAPI + Pydantic | Contracts, validation, authorization, business errors |
| ORM/migrations | SQLAlchemy + Alembic | Relations, transactions, constraints, evolution/compatibility |
| Database | PostgreSQL | Real integration tests, indexes/plans, backup/recovery |
| Vectors | pgvector | Persistent vectors, authorization filtering, model/dimension versions |
| AI | mock/local provider interface | Explicit mode, timeouts, schema/citation validation |
| Backend tests | pytest or suitable equivalent | Rules, real PostgreSQL, permissions, concurrency |
| Frontend tests | Vitest + React Testing Library | Interactions, errors, cache consistency |
| Browser tests | Playwright | Cross-role workflows and denied access |
| Environment | Docker Compose | New-environment startup, volumes, separated config |
| CI/CD | GitHub Actions | Tests, migrations, builds, controlled releases |
| Azure | Container Apps + Azure Database for PostgreSQL | Cloud config, logs, security, versions/recovery |
| Infrastructure | Prefer Bicep; Terraform only with an explicit reason | Repeatable creation/cleanup; one toolchain |
| Observability | Request IDs, structured logs, health, audit | Trace user action -> API -> job -> error |

Initial AI jobs use a PostgreSQL job table and separate single worker. Explicitly define leases, retry limits, idempotency, and restart recovery. This is a bounded learning implementation, not a claim of large-scale distributed scheduling.

## 6. Pages and interaction

1. Login/session state.
2. Ticket list with filtering, search, stable pagination.
3. Ticket details: public conversation, internal notes, status, AI drafts, citations, human review.
4. Knowledge: drafts, published versions, retrieval preview.
5. Management overview: backlog, categories, time to first human reply.
6. Audit/runtime details: actor, changes, model/knowledge versions, failure reasons.

Every core request has loading/empty/error/success states. Never display success after failure. Duplicate clicks must not duplicate sends. Handle expired sessions explicitly. Support keyboard use; connect field errors to inputs; color must not be the sole status signal.

## 7. States and consistency

| Object | States |
|---|---|
| Ticket | open / in_progress / waiting_customer / resolved / closed |
| AI job | queued / running / succeeded / failed |
| Suggestion review | pending / accepted / edited / rejected |
| Knowledge version | draft / published / archived |

M0 fixes role-specific transitions and reopening rules. Archive is a separate field, not a synonym for resolved/closed.

- ticket.version provides optimistic concurrency; stale writes return409.
- Status changes, events, and review actions remain transactionally consistent.
- Bind idempotency keys to identity/resource/content; reject changed content under the same key.
- Prevent duplicate review/public replies and recheck current permissions/knowledge availability.
- Persist UTC and display explicit timezones.
- Recover expired leases, cap attempts, and distinguish temporary/permanent failures.

## 8. Data model

| Table | Purpose |
|---|---|
| users | Identity, password hash, role, active |
| tickets | Requester, assignee, status, priority, version, archive, timestamps |
| ticket_messages | Author, public/internal visibility, body, timestamp |
| ticket_events | Ticket state and business changes |
| knowledge_articles | Logical identity, versions, publication/scope, hash |
| knowledge_chunks | Article version, source chunks, vectors, embedding model/dimension |
| analysis_jobs | Ticket/requester, idempotency/hash, state, lease, attempts, error |
| ai_suggestions | Category, suggested priority, draft, review, model/prompt versions |
| suggestion_sources | Source chunks/version/text/hash |
| audit_events | Actor, resource, action, outcome, request ID |

Knowledge history is immutable. Distinguish logical article IDs from version-row IDs. Showing historical references is separate from allowing the knowledge to be used now.

Choose indexes from actual queries. Compare fixed synthetic datasets with EXPLAIN and recorded environments; never invent speedup percentages.

## 9. Draft API

| Method | Path | Purpose |
|---|---|---|
| POST | /api/auth/login | Login |
| GET | /api/me | Current identity |
| GET/POST | /api/tickets | Authorized list/create |
| GET/PATCH | /api/tickets/{id} | Details/controlled update |
| POST | /api/tickets/{id}/messages | Reply/internal note |
| POST | /api/tickets/{id}/analysis-jobs | Idempotent AI job |
| GET | /api/analysis-jobs/{id} | Job status |
| POST | /api/suggestions/{id}/review | Human accept/edit/reject |
| GET | /api/knowledge/search | Authorized retrieval |
| POST | /api/knowledge/articles | Draft creation |
| POST | /api/knowledge/articles/{id}/publish | Version publication |
| GET | /api/dashboard | Management metrics |
| GET | /api/audit-events | Management audit |
| GET | /health, /ready | Process/dependency health |

M0 fixes fields, error codes, pagination, and role matrices. Server identity determines authors/requester_id. Keep 400/401/403/404/409 semantics consistent and document invisible-resource policy.

## 10. AI and evaluation

Models receive only currently authorized tickets and published knowledge. Instructions inside retrieved text are data, not permission changes or business commands.

Output: category, suggested priority, reply draft, citations, and items requiring human verification. Do not present uncalibrated confidence as certainty.

- No evidence: explicit human handoff, no invented repair steps.
- Provider unavailable: job failed, not falsely reported as insufficient knowledge.
- Invalid schema/citations: reject output, bound retries, preserve failure category.
- Validate document/chunk/version and contiguous original text, not only ID existence.
- A real citation does not prove every claim is supported; separately evaluate support manually.
- AI never automatically sends public replies or closes tickets.
- Logs exclude full tickets, credentials, and tokens by default.

Initial targets: synthetic role accounts, about 100 tickets and 20-30 knowledge articles; another 5,000 fixed-seed rows for SQL observation. These are target sizes, not claims of existing data.

Initial evaluation: 30 manually checked questions, 20 development / 10 holdout, plus separate authorization/injection/invalid-citation tests. Do not repeatedly tune against holdout data; disclose its use.

Record keyword/vector Hit@5, citation authenticity, claim support, refusal behavior, authorization, latency, and failure types. Report only measured examples, not market-wide or enterprise reliability.

First human response time is creation to the first human public reply. Exclude AI drafts and internal notes. Use elapsed calendar time initially; do not claim complex SLA support.

## 11. Azure delivery requirements

Azure is core to the portfolio version; local Docker is not a substitute.

| Area | Practice/acceptance |
|---|---|
| Container Apps | Deploy API/worker; document replica/runtime policy without HTTP traffic and verify the worker does not stall permanently |
| PostgreSQL | Persist business/vectors; verify region/network/extension allowlist/pgvector support |
| Registry | ACR or explicit alternative; bind images to commit SHA/version, not only latest |
| Identity/secrets | Managed Identity + Key Vault, least privilege, no frontend secrets |
| CI/CD | Release after tests; prefer OIDC with narrowly scoped deployment permissions |
| Infrastructure | Bicep or justified Terraform; separate parameters/secrets; cleanup instructions |
| Logs/troubleshooting | Azure Monitor/Log Analytics; trace a real failed request/job |
| Health/release | health/ready, version/revision, deployment smoke checks, application rollback |
| Recovery | Actually back up/restore and inspect records; app rollback is not database recovery |
| Cost | Verify pricing/resource scope before creation; budget alerts and cleanup checklist; alerts do not guarantee spending stops |

Full local mode: real PostgreSQL/embeddings/local model. CI: real PostgreSQL + mock model. Cloud demo: isolated synthetic data, explicitly labeled mock permitted, supplemented by real local inference evidence.

Deploying an application does not establish Azure AI model-service use. Adding a cloud model requires separate permission, cost, invocation, and evaluation checks. Do not assume a local 27B model should move to Azure.

Cloud resource creation/publication requires specific user authorization. Recheck current official documentation and compatibility during implementation.

## 12. Main checklist (planned at kickoff)

Complete dependencies in order. End each stage with commands, verification, limitations, and next steps.

| ID | Milestone | Deliverable/acceptance |
|---|---|---|
| S01 | M0 | Roles/stories and cross-user negative cases |
| S02 | M0 | ER/states/API and clear boundaries |
| S03 | M0 | Synthetic seeds, modes, sources |
| S04 | M1 | Scaffold, locks, config, health |
| S05 | M1 | PostgreSQL/migrations/FKs/constraints; empty DB upgrade |
| S06 | M1 | Authentication and role/object scope; invalid/expired tokens denied |
| S07 | M1 | Submit/assign/reply/transition; stale/illegal writes denied |
| S08 | M1 | Transactional audit; failures leave no false success |
| S09 | M2 | Typed React pages and four request states |
| S10 | M2 | Pagination/filter/cache; user switching isolation |
| S11 | M2 | Forms, duplicate submission, keyboard, narrow screens |
| S12 | M2 | Component/E2E reproducible three-role workflows |
| S13 | M3 | Knowledge versions/scopes; unpublished excluded |
| S14 | M3 | Keyword baseline and persistent pgvector; real vectors |
| S15 | M3 | Provider/timeouts/schema/failure classes |
| S16 | M3 | Durable jobs, leases, idempotency, restart recovery |
| S17 | M3 | Contiguous source citation validation; evidence-free refusal |
| S18 | M3 | Human review; duplicate requests do not duplicate public reply |
| S19 | M3 | Authorization/injection/knowledge-change regression |
| S20 | M4 | SQL plans/index experiment with environment recorded |
| S21 | M4 | Split evaluation, versions, limits |
| S22 | M4 | Full Compose/config/volumes/backup/restore |
| S23 | M4 | Real DB/migration/frontend/mock CI; regressions actually block merge |
| S24 | M5 | Azure/IaC/identity/secrets/deployment/cost |
| S25 | M5 | Cloud logs and actual failure tracing |
| S26 | M5 | Release/application rollback/data recovery exercises |
| S27 | M5 | README/ADRs/video/measurements/contribution evidence |

```text
S01 -> S02,S03 -> S04 -> S05 -> S06 -> S07 -> S08
S06,S07 -> S09 -> S10 -> S11 -> S12
S05,S06 -> S13 -> S14 -> S15 -> S16,S17
S08,S16,S17 -> S18 -> S19
S07 -> S20
S14,S17,S19 -> S21
S12,S18 -> S22
S12,S19,S22 -> S23
S22,S23 -> S24 -> S25 -> S26
S20,S21,S23,S26 -> S27
```

An initial estimate of 6-10 weeks at 8-10 hours/week covers the main track only, not a guarantee. Adjust to experience and actual acceptance; optional work is additional.

## 13. Optional MLflow / Spark / Databricks track

For data/ML roles; do not delay the software main track. Order: MLflow, PySpark, Databricks.

### D01: MLflow experiments

Use ticket classification or existing RAG/prompt evaluation. Use reliably labeled public/manually reviewed data. Synthetic data proves the workflow, not real-world generalization.

- Majority baseline, TF-IDF + logistic regression, then another method.
- Split by time/problem group to avoid similar-record leakage; use inference-time features only.
- Record data version, code SHA, parameters, Macro-F1, class recall, confusion matrix, runtime, artifacts.
- Save/reload the entire preprocessing pipeline; register versions and demonstrate switch/rollback.
- Acceptance: reproduce a run and explain mistakes/tradeoffs.

### D02: PySpark analysis

- Fixed-seed ticket/event/product data including duplicates, missing data, lateness, and invalid times.
- Explicit schema, deduplication, bad-row isolation, joins, windows, metrics, Parquet output.
- Idempotent reruns; verify small examples manually.
- Observe partitioning, shuffle, plans, and conditional performance comparisons.
- Deliver quality/correctness reports, rerunnable scripts, and observations; local mode is not cluster-management experience.

### D03: Databricks workflows

- Bronze raw -> Silver cleaned -> Gold metrics using Delta tables.
- Parameterized notebooks and multistep jobs; failure repair/rerun must not double count.
- SQL/dashboard metrics with traceable sources; practice permissions/lineage where supported.
- Free Edition is not Azure Databricks. Claiming Azure usage requires actual Azure execution and documented resources/permissions.
- Acceptance: reproducible end-to-end job, recovery behavior, environment limits.

Connect analytics through redacted exports, not a Spark dependency for every ticket request. Explain educational scope/cost when data is small; never assume Spark beats PostgreSQL/pandas.

## 14. Suggested directory layout (not yet created at kickoff)

```text
supportops-ai/
  README.md
  backend/                 # API, domain logic, worker
  frontend/                # React/TypeScript
  migrations/              # Alembic; actual layout may live under backend
  tests/                   # Backend and database tests
  e2e/                     # Browser workflows
  data/                    # Publishable samples and source policy
  evals/                   # Labels, evaluation scripts/results
  infra/                   # Bicep, deployment, cleanup
  scripts/                 # Startup, seed, backup, recovery
  docs/
    architecture.md
    permissions.md
    api.md
    adr/
    progress.md
    evidence/
  analytics/               # Optional PySpark/Databricks/MLflow
  .github/workflows/
  .env.example
  compose.yaml
```

At kickoff these sources/commands did not exist. After S04, document installation/startup/migration/seed/test/backup/cleanup commands only after verifying them.

## 15. Final acceptance and portfolio evidence

- [ ] Three-role workflow and API object authorization.
- [ ] Real PostgreSQL/migrations/transactions/conflicts/idempotency/job recovery.
- [ ] React four-state pages, cache consistency, component/E2E tests.
- [ ] Persistent vectors, authorized retrieval, versioned citations, refusal/human review.
- [ ] Manual evaluation labels, baseline, real outcomes/limitations.
- [ ] Reproducible environment, backup/restore, CI.
- [ ] Actual Azure deployment, identity/secrets/logs/release/rollback.
- [ ] Three real design tradeoffs or incident analyses.
- [ ] README distinguishes planned/implemented/verified and cloud AI mode.
- [ ] Owner can explain core modules, make a change, and verify it.

For each capability retain code, a meaningful test, execution/measurement evidence, a tradeoff, and contribution scope. Prioritize authorization, transactions, states, and recovery rather than implementation-mirroring tests for reversible styles.

Write resume claims after completion. Do not prefill Azure proficiency, production readiness, or invented speedups. This project does not automatically establish .NET, AWS, Intune, Copilot Studio, R/SparkR, enterprise tenant administration, or commercial employment experience.

## 16. Archived progress and next steps

| Item | Starting state |
|---|---|
| Requirements/architecture/27-stage checklist | Planned only |
| Azure acceptance | Defined here, not deployed |
| Data/ML extensions | Optional, unimplemented |
| New source/repository/cloud resources | Not created in planning session |

Suggested user prompt for a future conversation:

> Read this brief and continue SupportOps AI. Inspect the workspace, complete M0 roles/states/model/API, then implement the smallest M1 workflow. Report and verify each milestone; do not claim planned work is complete. Follow README stage order for Azure and optional data extensions.

This optional prompt was not authorization to begin development in the planning session.

## 17. Official references

- [React](https://react.dev/learn/managing-state)
- [FastAPI tests](https://fastapi.tiangolo.com/tutorial/testing/)
- [FastAPI JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [PostgreSQL EXPLAIN](https://www.postgresql.org/docs/current/using-explain.html)
- [pgvector](https://github.com/pgvector/pgvector)
- [TanStack Query](https://tanstack.com/query/latest/docs/framework/react/reference/index)
- [Vitest](https://vitest.dev/guide/)
- [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/)
- [Playwright](https://playwright.dev/docs/intro)
- [Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/get-started)
- [Key Vault and managed identity](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets)
- [Azure GitHub Actions](https://learn.microsoft.com/en-us/azure/container-apps/github-actions)
- [Azure logs](https://learn.microsoft.com/en-us/azure/container-apps/log-monitoring)
- [Azure pgvector](https://learn.microsoft.com/en-au/azure/postgresql/flexible-server/how-to-use-pgvector)
- [Spark quickstart](https://spark.apache.org/docs/latest/quick-start.html)
- [Spark tuning](https://spark.apache.org/docs/latest/sql-performance-tuning.html)
- [Azure Databricks](https://learn.microsoft.com/en-us/azure/databricks/introduction/)
- [Databricks Free Edition](https://docs.databricks.com/aws/en/getting-started/free-edition)
- [MLflow](https://www.mlflow.org/docs/latest/ml/getting-started/quickstart/)

This handoff is self-contained. Implementation follows current official documentation, the latest user instructions, and verified code rather than assuming archived plans are current behavior.
