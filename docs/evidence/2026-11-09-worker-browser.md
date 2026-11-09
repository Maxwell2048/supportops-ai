# Browser-to-worker execution

On 2026-11-09, 18 Chromium E2E cases passed across desktop and narrow viewports with an isolated PostgreSQL schema, real API and a separate mock worker process. New cases exercised no-evidence handoff and a published, indexed synthetic source flowing through the worker, human editing and a requester-visible public reply. The worker uses the application's normal claim and execution functions; only its test database connection is pointed at the isolated schema.

The first expanded run hit the production login limiter because the suite shares a single synthetic loopback client. The dedicated E2E fixture now uses higher synthetic-only limits; production limiter tests and defaults remain unchanged. A first version of the cited-reply test read the ticket before the review request finished. It was corrected to wait for the actual successful response. The fixture terminated its worker and removed the owned schema after the passing run.

The model remains deterministic mock generation. Real model end-to-end behavior and quality remain unverified.
