# S10 cache/filter/pagination acceptance

Date: 2026-10-27 (Australia/Perth). [Policy](../query-cache.md), [ADR0007](../adr/0007-session-query-cache-and-revalidation.md).

## Implemented

Pinned @tanstack/react-query 5.105.0 after npm registry version/peer checks; package-lock updated (two installed packages added, React 18/19 supported). Added session-owned QueryClient lifecycle, scoped keys, current-access revalidation, common list/detail invalidation, encoded search/status/priority filters, memory cursor stack, filtered-detail return navigation, cursor-error recovery, and a 10-case query suite. Removed the superseded useRemote hook. Extended only the test fixture helper with extra-ticket/session-duration parameters. Backend business rules/schema are unchanged.

## Actual checks

| Directory | Execution | Result |
|---|---|---|
| frontend | npm view @tanstack/react-query version peerDependencies --json | 5.105.0; React/types ^18 or ^19 |
| frontend | npm install --save-exact @tanstack/react-query@5.105.0 | 2 packages added; lock updated |
| frontend | npm ci, Vite stopped | 26 packages added, 27 audited; npm reported 0 vulnerabilities |
| frontend | npm run build | TypeScript/Vite 8.3.4 passed ; 70 modules; final recorded build 110ms |
| frontend | npm run test:api | 17 passed, 0 failed/skipped |
| frontend | npm run test:query | 10 passed, 0 failed/skipped |
| backend | uv run --locked python ../scripts/test_backend.py -q | 173 passed in 6.44s,0 skipped, actual PostgreSQL |
| Root | Docker helper/Compose wait | Engine 29.7.2 ready, existing DB healthy |

Early query assertions all passed, but Node remained alive because query GC timers retained the test process. Unsubscribing the observer alone was insufficient for a canceled query's finalizer. A Node-test-only timeout provider uses unref for Query timers; the suite then exited normally with 10 passing tests. No force-exit flag or product timeout weakening was used. An editing command initially hit Windows default text decoding; the affected App rewrite was reconstructed from its known clean UTF-8 baseline and subsequent reads/writes explicitly used UTF-8 before build/browser checks.

## Real browser evidence

Used the actual UI -> Vite 5173 -> FastAPI 8765 -> dedicated real PostgreSQL random schemas, with --extra-tickets 24 --session-minutes 10 --read-delay-ms 700 (arguments separated normally in the executed commands). No development tickets or real credentials were changed.

- Requester-a had 25 visible tickets; Next displayed page 2 with 5 rows after the 20-row first page. Fixture records share transaction timestamps, so UUID tiebreaking, not numeric sample order, determines pages.
- Opened a page 2 detail, returned, and still saw page 2/5 rows, after server revalidation.
- Applied search Pagination sample, status=open, priority=high from page 2: page 1/12 matching high-priority tickets, next/previous disabled. The hash URL contained those normalized filters.
- Detail navigation and Back to tickets restored the same filtered URL and 12 results.
- Changing status to resolved produced a clear no-match state with 0 rows, not the cached 12 rows.
- Disabling requester-a only in the owned fixture schema caused Refresh to receive401, clear the private workspace, and show login expiry feedback. Agent-b then saw its own empty list, with no prior-account rows/filters restored after explicitly returning to the unfiltered login link.
- Refreshing while loading, signing out, then signing in as agent-a produced agent-a's one assigned ticket; a previous delayed empty result did not replace it.
- Stopping the fixture backend and refreshing a previously successful cached list showed a safe502/retry card and removed the row. [Refetch-error screenshot](images/2026-10-27-s10-refetch-error.jpg).
- A final independent fixture run warmed page 1, navigated to page 2, disabled the synthetic account, then selected Previous: a new GET returned 401/invalid_session, request ID 3f0e5ad9-625b-4249-8423-8b56c73c811b. It returned to login instead of displaying the cached page. This confirms navigation revalidation; exact freshness timing is separately covered by the fresh-cache QueryObserver test rather than inferred from UI timing.

[Filtered-workspace screenshot](images/2026-10-27-s10-filters.jpg). Browser tabs, fixture API, and Vite were stopped. Each fixture shutdown printed owned-schema removal; the final owned-schema count was verified as 0 before publication. The ordinary development DB container remains running.

## Query suite assertions

Real QueryClient/QueryObserver tests cover identity/role/login/filter/cursor keys without JWTs; concurrent deduplication and fresh imperative cache reuse; separate sessions; clearing with an ignored late result; fresh-cache mount revalidation; failed revalidation masking old data; scoped invalidation of lists/details; one401 callback without retries; bounded freshness/GC configuration; filter URL validation/encoding and transmission. API17 tests remain independently passing.

No claim of measured performance gain, realtime revocation without a request, full browser matrix/WCAG, complete RTL/Playwright coverage, write forms, Azure/AI, or remote CI. CI is configured to run the new suite, not claimed executed. Stage message: [S10.txt](../commit-notes/S10.txt).
