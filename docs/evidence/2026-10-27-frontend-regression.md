# S12 execution: Component and real-database browser regression

Date: 2026-10-27 (Australia/Perth). These are new executions; S09-S11 evidence is retained unchanged.

## Implemented artifacts

- Pinned test dependencies/lockfile, Vitest/jsdom setup and12 rendered-component regressions.
- Playwright configuration and five scenarios in desktop1280x800/narrow390x844 projects, with no automatic retries.
- Reusable disposable fixture context and a Python runner that owns the real API/schema and propagates Playwright failure.
- Full test-source type check, npm commands, CI configuration, [testing guide](../testing.md) and [ADR0008](../adr/0008-component-and-isolated-browser-tests.md).

## Environment and commands

Windows PowerShell, Node22.23.2/npm10.9.8, Python3.14.7/uv0.12.10, Docker29.7.2 and the existing pinned PostgreSQL17.11 development container. The Docker helper returned ready and docker compose up -d --wait --wait-timeout60 db completed healthy. Only generated schemas in supportops_test were modified by browser tests.

Official npm metadata was checked for tool versions/engine/peer compatibility. Exact dev dependencies and the new Node engine minimum are recorded in the lockfile. npm ci completed with110 packages installed/111 audited and no vulnerabilities reported. A later package-lock-only update synchronized the Node engine declaration and reported155 audited packages/no vulnerabilities; it did not change application dependency versions. These npm counts differ between installed platform packages and complete lock metadata.

| Command | Actual result |
|---|---|
| backend: uv run --locked python ../scripts/test_backend.py -q | **177 passed, zero skips**,14.12s |
| frontend: npm run test:api | **17 passed** |
| frontend: npm run test:query | **11 passed** |
| frontend: npm run test:writes | **6 passed** |
| frontend: npm run test:components | **12 passed**, one file; final recorded run8.06s |
| frontend: npm run test:types | Passed, application + tests/configurations |
| frontend: npm run build | Passed,74 modules; final recorded Vite build119ms |
| frontend: npx playwright install chromium | Completed successfully; installed browser launched in real tests |
| frontend: npm run test:e2e | **10 passed**, final run20.2s; both viewport projects |

The first browser implementation passed8 tests. Pagination/skip-link assertions expanded this to10; subsequent runs passed10, including the documented npm-owned lifecycle. Production code and database migrations were unchanged in S12. Python fixture extraction was validated by actual whole-system execution, rather than counted as a backend business-rule change.

## Component assertions

Native labels/required fields/title autofocus and empty submission; local whitespace rejection with alert; synchronous duplicate-submit guard; exact creation body/key on uncertain retry; request cancellation/no late navigation after unmount;409 text retention with explicit review and new version/key; resolution retry retaining the original body after refreshed status becomes resolved; unavailable-agent retention/submission lock; mutation401 callback without automatic retry; loading/error gating that removes cached detail; failed-login password clearing; logout/account-switch cancellation with a late old requester response unable to enter the new agent workspace.

API methods are controlled doubles in this layer. They do not prove server authorization; the database/E2E suites provide that evidence.

## Actual E2E assertions

1. Requester keyboard creation -> manager assignment/priority -> agent start/internal note/wait/resume/resolve -> requester reopen -> agent resolve -> manager close/archive/unarchive/reopen. Requester cannot see the internal note or staff activity; archived forms have no requester actions; reopening a closed ticket clears assignment and the former agent receives actual404. Final narrow layout has no document-level horizontal overflow, and Tab reaches the reply button.
2. Manager assignment selected before a concurrent requester reply returns actual409, retains the selected agent, and cannot submit until explicit version review. A separate public reply draft survives another actual conflict and submits only after review.
3. A real creation commits201 before an injected503 replaces the browser acknowledgement. Retry uses the same key/body and returns one ticket; double-clicking reply produces one network write and one visible reply. The list contains one matching creation.
4. An agent's unmatched filter produces an empty state; agent-b/requester-b direct seed-ticket URLs receive actual404. A controlled delayed503 refresh shows loading and removes previous detail before an error; sign-out removes private controls and browser storage remains empty.
5. Search returns20+4 pagination fixtures. Returning from page2 detail preserves its four rows. Open/high filters reset to page1 with12 rows and both paging buttons disabled. Native Tab/Enter activates Skip to content and focuses main in both viewport projects.

[Desktop sample](images/2026-10-27-s12-e2e-desktop.png); [narrow sample](images/2026-10-27-s12-e2e-narrow.png). Screenshots contain only synthetic information. An early full-page capture from a scrolled position composited an offscreen fixed skip link into the image; the capture now scrolls to document origin first. Regenerated samples were inspected. This was corrected in the test capture, without changing application UI.

## Failure propagation and cleanup

An intentional negative control ran npm run test:e2e -- --project s12-intentional-invalid-project. Playwright rejected that nonexistent project with exit1, and the runner still printed owned-schema removal. The caller explicitly checked that1 was the expected result; this is not reported as a passing business test or hidden regression.

All successful runs also printed owned-schema removal. Final database inspection confirmed zero test_s09_browser_* schemas; no8766/5174 listeners remained. An initial ad-hoc cleanup query lacked the src import path and did not execute; it was rerun with the same source-path bootstrap as the helpers. Reports/results are ignored, traces/videos are off, and only reviewed synthetic PNG samples are published.

## Limits

Remote GitHub Actions/Linux execution has not been verified. CI now includes the new commands and a dedicated PostgreSQL service for the web job, but configuration is not execution evidence. One Chromium engine/two sizes, selected keyboard assertions and component error alerts do not establish WCAG/screen-reader compliance or exhaustive browser coverage. No coverage percentage, performance gain, production cloud, AI or knowledge implementation is claimed. Abrupt machine/process failure can prevent fixture cleanup. Next is S13 knowledge versioning/publication/authorization.
