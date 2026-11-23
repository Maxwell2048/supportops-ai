# Controlled read-only tool use verification

Implemented: an allow-listed `search_knowledge` and `ticket_history` tool loop for analysis jobs, per-call lease renewal and access re-checks, a call budget, an additive baseline search, migration 0010 for the stored trace, the `tool_calls` suggestion field and a review-workspace list. See [design](../agent-tools.md) and [ADR 0011](../adr/0011-controlled-read-only-tool-use.md).

## Automated checks on 2026-11-23

- Backend: 339 tests passed with zero skips against local PostgreSQL 17 through `scripts/test_backend.py`, which uses a dedicated `_test` database and isolated schemas. This includes 10 new planner contract tests, 4 loop unit tests and 10 new integration cases.
- The integration cases cover: mock planning with history and cited evidence; exclusion of internal notes from planner and drafter input; rejection of an unknown write-like tool, an extra `ticket_id` argument and a mistyped query, with the ticket left unchanged; budget enforcement; per-call denial after reassignment, deactivation or a ticket version change; a lost lease stopping without a result; the legacy provider path; and restricted knowledge never reaching the planner.
- One existing citation test subclass was updated to the extended `generate(ticket, evidence, context)` contract. Before the update, the old signature raised `TypeError` and the job failed safely as `invalid_output`.
- Frontend: clean `npm ci`, `npm run build`, `npm run test:types`, 19 component tests (2 new), 17 API, 11 query and 6 write tests passed.
- Browser: 24 Chromium cases passed across desktop and narrow layouts with an isolated schema, real API and a separate mock worker. The cited-reply case now also checks the listed knowledge search and ticket history calls. The owned schema was removed afterwards.

## Local model check on 2026-11-23

I ran `scripts/check_local_worker.py` with local Ollama 0.33.3 and `huihui_ai/qwen3.5-abliterated:4b` (digest `9acbd90c…003e6`, the model from the [earlier pinned-worker check](2026-11-09-pinned-worker.md)) against disposable synthetic schemas. The Ollama server I started for the check was stopped afterwards.

On the final code, all three runs succeeded with one validated citation each. In every run the model called `ticket_history` and its own `search_knowledge`. Its keyword queries, for example "browser access error sample dashboard", returned no passages, and the server baseline title search supplied the evidence. In two runs the model's second round requested limits above the allowed bounds and was rejected with `limit:less_than_equal`; it did not correct this within the budget. Categories varied between `bug` and `access`.

Earlier runs during development, before the baseline and rejection-detail changes, also showed a cold-start timeout that was re-queued as transient, one draft rejected as `invalid_citation`, and one request for a non-existent `thread_reply` tool, which the server rejected as `tool_not_allowed`. In one run before the baseline became mandatory, the model's empty search caused an evidence-free handoff; this motivated the additive baseline.

## Limitations

These runs are a smoke check with one ticket, not an evaluation. They do not establish model quality, query quality, adversarial robustness, latency targets or license provenance. Keyword search requires all query terms, which made the model's broader queries miss. The development database was not migrated in this stage; run the documented migration before starting the API against it.
