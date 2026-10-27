# S12: Component and browser regression

Date: 2026-10-27 (Australia/Perth). [Execution evidence](evidence/2026-10-27-frontend-regression.md); [test-layer decision](adr/0008-component-and-isolated-browser-tests.md).

## Test layers

| Layer | Tools | Purpose | Boundary |
|---|---|---|---|
| Database/API | pytest, real PostgreSQL/Alembic | Current role/object authorization, transactions, audit, idempotency, concurrent writes | Does not prove rendered interaction |
| Client/query protocol | Node test runner, actual QueryClient | Safe DTOs/errors, encoded filters, cache lifecycle, keys and invalidation | No rendered browser |
| Components | Vitest/jsdom, React Testing Library/user-event | Native labels/validation, pending guards, drafts, exact-body retry, unavailable selections, mutation expiry and late-response isolation | API methods are controlled test doubles; not server-authorization evidence |
| E2E | Playwright Chromium, actual React/API/PostgreSQL | Three-role lifecycle, conflict review, server object scope, paging, desktop/narrow keyboard behavior | One browser engine, two viewports; selected transport faults are explicit injections |

Pinned dev dependencies are recorded in package.json/package-lock.json: Vitest5.0.5, Playwright1.64.1, React Testing Library16.3.3, user-event14.6.8, jest-dom7.0.1, DOM Testing Library10.4.1, jsdom30.1.3 and Node types22.19.15. The declared Node minimum now matches jsdom:22.22.2 for22.x or24.15.0 for24.x. Actual execution used Node22.23.2. Python dependencies did not change.

## Local commands

Start the configured PostgreSQL container and prepare the dedicated test database. From backend:

```powershell
uv run --locked python ../scripts/test_backend.py -q
```

Stop any owned Vite server before clean installation on Windows. From frontend:

```powershell
npm ci
npm run test:api
npm run test:query
npm run test:writes
npm run test:types
npm run test:components
npm run build
npx playwright install chromium
npm run test:e2e
```

The test:types command includes tests/configs rather than only application sources. Components run once by default; use npx vitest for watch mode. E2E accepts Playwright arguments, for example npm run test:e2e -- --project chromium-narrow. Do not run bare Playwright against an arbitrary existing API; the npm command owns the isolated fixture lifecycle.

## E2E ownership and data

scripts/test_frontend_e2e.py reuses the manual fixture context from serve_frontend_check.py, requiring localhost PostgreSQL and a dedicated database ending in _test. It generates a random schema, runs real migrations, activates five synthetic fixture accounts, and creates24 pagination cases. It binds its own API to127.0.0.1:8766 and refuses an occupied API port. Playwright owns a separate Vite server at5174 with an explicit API proxy and reuseExistingServer=false. Existing development servers/data are not adopted or reset.

The runner launches Playwright directly through Node, propagates its exit code, stops the owned API thread, then drops only its generated schema in a context-manager finally block. Playwright stops its Vite/browser processes. Normal success and an intentionally rejected project selection were exercised locally. Forced process termination or machine failure can prevent cleanup; inspect the dedicated test database before removing a leftover generated schema. Never drop public/development tables as test cleanup.

Tests use one worker, no retries, fresh browser contexts per test/role and unique created ticket titles. Projects share only immutable seed/pagination fixtures; business workflows create their own tickets. This avoids depending on execution order while keeping lock/concurrency behavior in the real API. Desktop1280x800 and narrow390x844 run the same five scenarios. The synthetic password is public fixture data; production credentials are neither passed as arguments nor captured in browser storage.

The lost-acknowledgement case first forwards creation to the real API and receives201, then deliberately returns503 to the page. Its second call reaches real persistent idempotency. The failed-refresh case explicitly injects503 after delaying a read to assert that loading/error views remove previous private content. These injected transport outcomes do not claim a real infrastructure outage. Role/object denials in the suite come from the actual API, not intercepted responses.

## Reports, screenshots and CI

Playwright HTML reports and test-results are ignored. Traces and videos are off: traces can contain bearer headers. Failure screenshots and selected successful synthetic screenshots stay local; two reviewed samples are published with the evidence. They are examples, not visual snapshot baselines or a full accessibility audit. The report from a negative harness check may replace a prior HTML report; the dated evidence distinguishes each execution.

CI now configures the component/type/browser commands, pinned runtime, a separate PostgreSQL service for the web job and Chromium system dependencies. Local Windows success does not prove a hosted Linux run passed. S23 still owns complete CI/mock/migration/release policy and branch protection. Firefox/WebKit, screen-reader testing, WCAG conformance, coverage percentages and exhaustive transition/device matrices are not claimed.

Official setup references: [Vitest configuration](https://vitest.dev/config/), [Testing Library setup](https://testing-library.com/docs/react-testing-library/setup/), [Playwright web server ownership](https://playwright.dev/docs/test-webserver).
