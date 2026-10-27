# S11 verification: Ticket forms and write recovery

Date: 2026-10-27 (Australia/Perth). This record reports new execution; previous stage outcomes retain their original evidence.

## Implemented

Role/state-scoped create/reply/transition/assignment/priority/archive forms, typed POST/PATCH responses, manager-only active-agent directory, payload-bound attempt keys, synchronous duplicate guards, retained drafts across revalidation/conflicts, explicit version review, safe uncertain-result retries, mutation401 expiry and cancellation. See [form policy](../forms.md).

## Commands and local results

Windows; Python 3.14.7, Node 22.23.2, existing pinned dependencies. Docker was initially stopped. scripts/start-docker.ps1 successfully recovered Engine 29.7.2; docker compose up -d --wait --wait-timeout 60 db completed healthy. No volumes, credentials or development records were reset.

- backend: uv run --locked python ../scripts/test_backend.py -q: **177 passed, zero skips**, 8.36 seconds. Four new directory tests cover missing auth, requester/agent denial, active-agent projection, disabled target removal and current manager-role recheck. The existing ticket authorization/concurrency/idempotency suite also ran.
- frontend: npm ci: **26 packages installed, 27 audited, zero vulnerabilities reported**. No dependency/version changes; package-lock.json is unchanged.
- frontend: npm run build, npm run test:api, npm run test:query, npm run test:writes: final results recorded after final verification below. Tests use actual QueryClient/MutationCache behavior and typed transport functions, not a full rendered component suite.
- Language guard and git diff --check run before publication. Commit/push results are verified separately through Git; workflow configuration is not a remote CI result.

## Real browser and PostgreSQL checks

Both runs used scripts/serve_frontend_check.py on 127.0.0.1:8765 with real migrations/business services in owned random schemas in supportops_test. Vite used the matching server-side proxy. Only public synthetic accounts/passwords were used.

First run: --session-minutes 30 --read-delay-ms 200.

1. Requester created [S11 browser] Synthetic request workflow using native keyboard Tab/Enter. Ticket fec52324-9125-4aae-9b24-3b4c3b1f5972 started open/version1, with server-selected owner and no messages.
2. Requester typed a reply at version1; another browser session's manager assigned agent-a, producing version2. The requester received409/request4083d4b3-2c3b-416d-8ddd-7c4f0c9714d8. Text remained intact, current2/draft1 were displayed, submission was blocked until explicit review. After review/separate submit, exactly one public reply appeared at version3. [Conflict screenshot](images/2026-10-27-s11-conflict.jpg).
3. Agent-a started work (v4), added an internal note (v5), and resolved with an atomic public reply (v6). Manager closed (v7), archived (v8), unarchived (v9), then reopened with a public reason (v10/open/assignee cleared). Refreshing the former agent returned404. Requester saw three public messages and no internal note; staff saw all four messages.

Second run: --session-minutes 30 --lose-first-write-response --write-delay-ms 1000.

1. Requester double-clicked creation. The API committed successfully, then fixture middleware replaced the first success response with503. Title/body remained visible and locked; Retry same request recovered ticket20d5c144-c281-4142-8a65-ddf568ba2f6e at version1. The list contained one matching title. [Uncertain-result screenshot](images/2026-10-27-s11-retry.jpg).
2. Double-clicking a public reply produced one visible message and version2. A direct read of only the owned test schema confirmed **one matching ticket, one message, two ticket events and two audit events**. The ticket-scoped idempotency row count was1; creation uses the separate collection resource, so it is intentionally excluded from that scoped count.
3. Manager selected agent-b for stable fixture ticket704ad20c-bb80-535f-888e-f503a1656df0 at v4. Concurrent requester reply made v5. Assignment returned409/request956aa185-24d6-4fd6-9e07-10870bd5bc7c; **agent-b remained selected** with current5/draft4 until review. [Assignment conflict](images/2026-10-27-s11-assignment-conflict.jpg). This verifies A05 input preservation for an actual assignment selection, not only a text reply.
4. After review, test-only SQL disabled only agent-b in that owned schema. Submission returned422/requesta0550a52-77d8-4273-ad51-16c8be301f51 with an unavailable-agent prompt. Refresh removed agent-b from available choices; the retained choice showed explicitly unavailable and submission was disabled. No auto-assignment occurred.
5. Initial viewport requests appeared ineffective: DOM measurements still showed1280x720, so those observations were not counted as narrow acceptance. The manager tab later measured **innerWidth390, innerHeight844, document scrollWidth375**; the real narrow screenshot showed wrapping error text, reachable native controls and a visible keyboard focus ring after Tab. The stale native selection initially appeared unassigned after refresh; this was fixed and checked again with the explicit unavailable option. [Final narrow form](images/2026-10-27-s11-unavailable-agent.jpg). The viewport override was reset.

## Final verification and cleanup

Final frontend totals: **17 API tests, 11 query/mutation tests and 6 write tests**, all passing; production build passed with74 modules. The build includes the final stale-agent selection fix. During development, changing effect dependencies through hot reload produced a transient development warning; the effect has a fixed dependency list in the saved source. The write hook was then extracted to hooks/useTicketWrite.ts to keep component-only exports compatible with React Fast Refresh; the subsequent TypeScript/production build passed (74 modules, 110ms Vite build). This extraction changes module boundaries, not the verified write logic. No backend business/schema changes were made after the177-test execution. Fixture-only failure switches are exercised by the second real browser run.

Both temporary API instances were stopped with Ctrl+C and printed owned-schema removal. A final database query confirmed **zero** remaining browser fixture schemas. Vite was stopped and no5173/8765 listeners remained. Development data was not modified. Publication checks include the English language guard, diff whitespace, Python syntax, relative Markdown links and supplied author identity.

## Limits and next stage

The complete status-transition/browser matrix, rendered component tests, automated focus/validation assertions, broad device/browser/accessibility coverage and repeatable Playwright scenarios remain S12. This is one real narrow-form check, not WCAG conformance. Drafts are intentionally page/session memory only. An abrupt browser/process exit can lose recovery state. No server directory pagination, phone-field persistence, account administration API, production/cloud/AI or remote CI validation is claimed.
