# S16 analysis job verification

Executed 2026-11-07 with a dedicated PostgreSQL test database. The full backend suite passed 279 tests with zero skips. Tests cover idempotency, current access, API create/read, retry exhaustion, independent connections and row locks, lease renewal, expired token fencing and a separate mock worker process reclaiming an expired job. The process test simulates database lease expiration; it does not kill a worker during an active model call.

Frontend npm ci and production build passed after transient Windows file-lock failures and a dependency reinstall. Development migration 0005 to 0006 completed in a transaction; row counts in 13 existing tables matched before and after. This check compares row counts, not every value.

The worker uses a mock provider and no knowledge retrieval. Its stored output is not exposed by the job API. Real inference, citation validation, human review, deployed operation and full crash timing remain unverified.
