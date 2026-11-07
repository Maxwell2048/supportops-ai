# Analysis jobs

Managers and assigned agents can create durable jobs with a ticket version and Idempotency-Key. The job read endpoint checks current ticket access and returns status, attempts and safe error category. Raw draft results are not exposed in S16.

From the backend directory in PowerShell, set PYTHONPATH to src and run uv run --locked python -m supportops.job_worker. Stop with Ctrl+C. Pass --once for one polling iteration. The worker uses the deterministic mock provider and authorized keyword retrieval.

Claims use row locks and skip locked rows. Each claim has a fresh token, 180-second lease and at most three attempts. Expired claims can be reclaimed. Renewal and completion require the current unexpired token. Temporary failures retry after 10 or 20 seconds. The worker rechecks actor access and ticket version before processing and completion. Stored model output is not a verified citation.

See [verification](evidence/2026-11-07-analysis-jobs.md). Citation checks are described in [citation policy](citations.md). Human review remains S18. Real model inference and production worker operation remain unverified.
