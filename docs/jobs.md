# Analysis jobs

Managers and assigned agents can create durable jobs with a ticket version and Idempotency-Key. The job read endpoint checks current ticket access and returns status, attempts and safe error category. Raw draft results are not exposed in S16.

From the backend directory in PowerShell, set PYTHONPATH to src and run uv run --locked python -m supportops.job_worker. Stop with Ctrl+C. Pass --once for one polling iteration. The default worker uses the deterministic mock provider and authorized keyword retrieval. To use a local model explicitly, pass `--model NAME --digest FULL_SHA256`; both are required together. The adapter verifies the model digest before and after inference, and the job records provider provenance. Review model licensing and quality before use.

Claims use row locks and skip locked rows. Each claim has a fresh token, 180-second lease and at most three attempts. Expired claims can be reclaimed. Renewal and completion require the current unexpired token. Temporary failures retry after 10 or 20 seconds. The worker rechecks actor access and ticket version before processing and completion. Stored model output is not a verified citation.

See [verification](evidence/2026-11-07-analysis-jobs.md). Citation checks are described in [citation policy](citations.md). Human review remains S18. A local synthetic worker check is recorded in [pinned worker evidence](evidence/2026-11-09-pinned-worker.md). Production operation and model quality remain unverified.
