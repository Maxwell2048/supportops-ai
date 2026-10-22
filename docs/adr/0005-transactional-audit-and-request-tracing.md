# ADR 0005: Atomic success audit and redacted failure logs

Date: 2026-10-22. Status: accepted, locally implemented/verified in S08. [Evidence](../evidence/2026-10-22-audit-verification.md).

Problem: business events alone cannot associate an effective write with an HTTP request. A separate post-commit audit write could fail after the business change succeeds.

Decision: append AuditEvent where the business event is created, using the same transaction. Enforce unique resource_id/ticket_version. Successful idempotency replays return the cached result without a second audit. Store execution-time role and server request ID; use an explicit change allowlist instead of copying free text. Manager queries use identity/filter-bound signed cursors.

Failures cannot be stored in the transaction about to roll back, nor represented as successes. Independent JSON request logs record status and safe codes for denials, conflicts, database errors, and unexpected failures. Unexpected exceptions expose no original text/traceback. Disable raw access logs to limit query-string leakage.

Tradeoffs: additional indexes and one audit insert per effective write. Failure logs are not persistent yet. No fabricated historical request IDs. Client APIs cannot edit/delete audit, but a privileged development DB administrator can. Least privilege and cloud logging require later verification.
