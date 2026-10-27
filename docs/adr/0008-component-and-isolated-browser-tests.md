# ADR0008: Separate controlled component tests from isolated real-API browser tests

Date: 2026-10-27. Status: accepted for S12.

## Context

S09-S11 delivered readable workflows and manual evidence, but another developer needed repeatable checks for draft retention, duplicate sends, authorization changes and multi-role state transitions. A component mock can reproduce a lost response precisely, but cannot establish PostgreSQL authorization/transaction correctness. Browser-only tests would make every failure harder to isolate.

## Decision

Keep the existing pytest and Node protocol suites. Add Vitest/jsdom/Testing Library for rendered behavior with controlled API methods, and Playwright Chromium for actual React/FastAPI/Alembic/PostgreSQL flows. Pin compatible versions and type-check the test sources/configuration.

Use a Python-owned fixture context so normal Windows/Linux completion and test failure both close the API before dropping its generated test schema. Playwright owns its Vite process; neither service reuses an existing development server. Run sequentially against one isolated schema with immutable shared fixtures and independently created business tickets. Use separate browser contexts for roles and run the scenarios at desktop and narrow widths without automatic retries hiding intermittent failures.

Use real server authorization for negative object cases. Explicitly label intercepted503/lost acknowledgements as transport injections. Disable traces/videos to avoid bearer capture; keep reports ignored and publish only selected synthetic screenshots. CI configuration is separate from verified CI execution.

## Consequences

Fast deterministic component regressions complement a slower whole-system check. The suite requires a prepared localhost test database, Node/Python runtimes and installed Chromium. A context-manager finally block handles normal test failures, but cannot guarantee cleanup after machine failure or forced process termination. One engine/two widths and selected keyboard assertions do not prove broad accessibility/browser compatibility. This stage changes no application business rules or database migrations.
