# SupportOps AI delivery handbook

Last reviewed: 2026-11-09 (Australia/Perth).

This handbook records the delivered local workflow, evidence, and remaining work. The project is a synthetic portfolio application. Generation defaults to a deterministic mock and supports an explicitly pinned local Ollama model. A draft requires a staff decision before a public reply can be created.

## Delivered workflow

1. Start the local PostgreSQL service and apply the current migrations as described in [database operations](database.md). Configure authentication using [local authentication](auth.md). Keep local credentials in the ignored environment file.
2. Start the API and frontend using the commands in the [README](../README.md). Sign in with an activated synthetic account. Requesters can create and follow their own tickets. Agents see tickets currently assigned to them. Managers can assign agents and manage ticket state.
3. Managers can use the Knowledge workspace to create drafts, index, publish and archive current versions. The [knowledge guide](knowledge.md) and [retrieval guide](retrieval.md) also describe the API and historical operations.
4. Start the local mock worker from the backend directory by setting PYTHONPATH to src and running `uv run --locked python -m supportops.job_worker`. Keep that terminal open. The worker polls durable jobs. Stop it with Ctrl+C. The [job guide](jobs.md) documents the lease and retry policy.
5. Open a ticket as the assigned agent or manager. The Suggested response panel starts analysis and shows recent job statuses. Accessible published knowledge must be indexed. Review the source quotation and response. Accept, edit or reject the suggestion. An evidence-free handoff can only be rejected through the suggestion workflow; staff can write a separate reply.
6. If the browser cannot determine whether a review request succeeded, use Retry previous request while the panel remains open. This resends the same key and payload. Job history is available after navigating back, but an unfinished client-side retry attempt is not persisted across page reloads.

## What has been verified

- PostgreSQL ticket, knowledge, retrieval, job and review tests use isolated synthetic schemas. See [review backend evidence](evidence/2026-11-09-review.md) and [security evidence](evidence/2026-11-09-analysis-security.md).
- The review interface has component coverage and desktop/narrow Chromium coverage. Its dedicated browser scenario uses mocked synthetic analysis responses. Existing ticket and knowledge browser scenarios use an isolated API and PostgreSQL fixture. See [UI evidence](evidence/2026-11-09-review-ui.md).
- S14 separately exercised real 384-dimensional local embeddings and pgvector with synthetic inputs. This does not verify a real generation model. See [retrieval evidence](evidence/2026-10-27-retrieval.md).
- A separate local generation adapter smoke check returned structured output and a matching synthetic quotation, but misclassified the sign-in example. The default worker uses a mock. An optional pinned-model worker was exercised separately; see [worker evidence](evidence/2026-11-09-pinned-worker.md).
- Each GitHub Actions result belongs to a particular commit. The failed remote browser run and its correction are recorded in [CI follow-up](evidence/2026-11-09-ci-followup.md). Check the current commit's Actions page before asserting its result.

## Work remaining

| Area | Required work and acceptance evidence |
|---|---|
| S19 security | Expand concurrent reassignment, publication change, prompt injection and malformed citation regressions. Evaluate actual model behavior with a fixed synthetic adversarial set. Verify that API authorization and human review remain effective independently of model output. |
| Real generation | Select an explicitly licensed local generation model and record its exact digest, context settings and license. A pinned local worker and synthetic end-to-end check exist. Select and evaluate a suitable model, verify license provenance, measure failures and document resource requirements before use. The default remains mock. |
| S20 SQL experiments | An initial 5,000-row temporary-table observation is documented in [SQL evidence](evidence/2026-11-09-sql-experiment.md). Extend it to full ticket rows and application queries, vary the workload, measure write cost and repeat observations before proposing an index change. |
| S21 AI evaluation | Create and manually review the planned development and holdout questions. Version the data, retrieval and prompt settings. Measure retrieval, citation authenticity, claim support, refusal and latency without tuning repeatedly on the holdout set. |
| S22 operations | Complete application and worker Compose configuration, startup checks, backup and restore. Exercise a restore into an isolated database and verify representative records. Keep the development password and existing data intact. |
| S23 CI and protection | Add the remaining worker, review and recovery checks to CI and verify failures block the intended branch. Configure branch protection in GitHub and record actual settings and permissions. |
| S24 Azure | Obtain explicit approval for subscription, region, resource scope and cost before creating chargeable resources. Validate the current Azure service and pgvector requirements, provision with reviewed infrastructure code, use managed identity and secrets, deploy synthetic data and record the actual resource inventory and cleanup. |
| S25-S26 operations | Verify cloud logs with a real controlled failure. Exercise application rollback and a separate database restore. Record commands, results, access controls and cleanup. |
| S27 delivery | Refresh architecture, design decisions, contribution notes, screenshots and a demonstration video after the implementation is verified. Report real measurements and limitations. |
| Product interface | Add historical-version browsing, vector indexing, broader keyboard and screen-reader testing, and real-model worker evaluation. The independent mock worker is covered by [browser evidence](evidence/2026-11-09-worker-browser.md). |

## Validation and publication

Run the backend and frontend commands from their stated directories in the README. A skipped database test is not database validation. Use only synthetic or explicitly licensed content and keep secrets out of logs, examples and screenshots. Run `python scripts/check_repository_language.py` before publishing. For every stage, record implementation and execution evidence separately, prepare an English first-person commit note in `docs/commit-notes/`, commit with the supplied Maxwell identity, push, and inspect the GitHub Actions run for that exact commit.

## Troubleshooting

- If readiness reports an outdated schema, verify the target database and migrate according to [database operations](database.md). A migration is not a backup.
- If analysis stays queued, check that the separate worker is running and using the same database. The worker is currently mock-only.
- If analysis reports incomplete retrieval, index every currently accessible published knowledge version before retrying. Drafts are not search candidates.
- If a suggestion is stale or unavailable, re-run analysis. Ticket edits, assignment changes, source archive/scope changes, or an older unmarked result can require reanalysis.
- If frontend dependency installation encounters a Windows file lock, stop project-owned development processes and retry. Do not terminate unrelated processes. Browser tests require the Chromium build installed by Playwright.
- If Docker Desktop is unavailable, use the repository startup guidance and inspect the local engine state. Do not reset volumes to solve a connection problem.
