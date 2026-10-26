# S09 typed frontend acceptance

Date: 2026-10-27 (Australia/Perth). Code/operations: [frontend guide](../frontend.md), [ADR0006](../adr/0006-frontend-session-and-request-boundaries.md).

## Implemented

Typed/runtime-validated API client; memory-only login/session; role-scoped list and detail pages; public/internal message distinction; staff activity; loading/empty/error/success UI; safe request-ID error cards; basic cursor navigation; deadline/cancellation/late-response isolation; explicit Perth timestamps; responsive CSS and English copy. A Vite API-target override supports 8765 without touching unrelated processes. No write forms or AI UI were added.

## Actual command results

| Directory | Command | Result |
|---|---|---|
| Root | pwsh -NoProfile -File scripts/start-docker.ps1 | Engine 29.7.2 ready |
| Root | docker compose up -d --wait --wait-timeout 60 db | Existing database container healthy |
| backend | uv run --locked python ../scripts/test_backend.py -q | **173 passed in 7.05s, zero skipped**, real PostgreSQL |
| backend | uv lock --check | 38 packages resolved; lock consistent |
| frontend | npm ci, after stopping Vite | 24 packages added; 0 vulnerabilities reported for this run |
| frontend | npm run build | TypeScript/Vite 8.3.4 passed, 24 modules; recorded Vite build 124ms |
| frontend | npm run test:api | **17 passed, 0 failed, 0 skipped** |
| backend | serve_frontend_check.py, then --read-delay-ms 1200 | Real API and migrations in two successive owned random *_test schemas; both cleaned on exit |
| Root | PostgreSQL owned browser-schema count after exit | 0 |

An initial npm ci attempt while Vite was running failed with Windows EPERM unlinking its loaded native rolldown binding. The owned Vite process was stopped, clean install retried successfully, then build/API tests reran. No dependency change or administrative reset was used to conceal the failure. Newly added frontend sources were formatted using temporary pinned Prettier 3.6.2; the final build and all 17 API tests passed again afterward. The native browser screenshot bytes were JPEG and are stored with matching .jpg filenames. A final requester-only wording refinement uses Support team/Awaiting assignment instead of personnel IDs; TypeScript and the production build passed again after that presentation change.

## Real browser checks

The in-app browser exercised the actual UI through Vite 5173 -> FastAPI 8765 -> isolated real PostgreSQL. It used five publicly labeled synthetic fixture accounts, not development credentials. Screenshots show the narrow in-app viewport; desktop-wide/cross-browser acceptance is not inferred.

1. Requester-a login: one own ticket, one public reply, no internal note or Activity section. Literal `<img src=x onerror=alert(1)>` remained visible text, not executable markup.
2. Agent-a login: the assigned ticket contained both public reply and clearly labeled internal note, plus versions 1-4 activity.
3. Manager login: both requesters' tickets appeared. [Manager screenshot](images/2026-10-27-s09-manager.jpg).
4. Agent-b login: empty list. Navigating directly to ticket 704ad20c-bb80-535f-888e-f503a1656df0 showed unavailable404 with request ID 9eb0c8c7-4bd7-4816-840f-44c66c23341b. No title/body from the unauthorized ticket appeared. [404 screenshot](images/2026-10-27-s09-unavailable.jpg).
5. Wrong password:401 with safe prompt and request ID 8de2e6f3-db3a-4f91-b547-94af97812049; login did not succeed and password field cleared.
6. Reload returned to login, confirming no persisted token. Sign-out removed the private workspace before the next login.
7. With 1200ms fixture delay: Loading tickets was visible; refreshing then signing out while loading and signing in as agent-b produced only agent-b's empty state. The previous account's delayed result did not restore its list.
8. The one-minute fixture session expired without another request, returning to login with an expiry notice. [Expiry screenshot](images/2026-10-27-s09-expired.jpg).
9. Requester-b saw only its separate private ticket and a no-replies conversation state.
10. The synthetic manager was disabled only inside the owned test schema. Refresh returned real401/invalid_session, request ID 6fd685c6-e027-4e6a-b998-aebea9ca0672, and removed the workspace before its one-minute client deadline.
11. Stopping the fixture backend and refreshing replaced the successful list with a safe502 proxy error/retry card; it did not keep displaying success or fabricate an API request ID. [Offline screenshot](images/2026-10-27-s09-offline.jpg).

The fixture service and Vite were stopped after verification, the browser tab closed, and owned test schemas counted0. Existing development tickets/accounts were not modified; test-only manager disabling occurred only in the random schema. The normal database container remains running.

## Automated protocol coverage

17 Node tests cover email normalization; credentials only in JSON; no cookies/cache/redirects; bearer header without URL token; unknown-field stripping; cursor encoding; role projections;401/403/404/409/422/429/503 safe errors; invalid DTOs; HTML proxy failures; invalid local paths; cancellation;15-second deadline machinery with a short test deadline; network errors without exception reflection.

These are API-client tests and real manual browser checks, not a completed component or Playwright E2E suite.403/409/422/429/503 client mapping is unit-tested; no claim that each was induced through the browser UI. Multi-page browser navigation, full accessibility/keyboard, persistent caches/filters, deployment, cloud, AI, and remote CI remain later work.

## Publication

The first-person English message is saved in [S09.txt](../commit-notes/S09.txt). Repository character/syntax/link/credential/whitespace checks run before commit; actual commit/push is verified through Git rather than inferred from this document. CI now includes npm run test:api, but remote execution is not yet verified.
