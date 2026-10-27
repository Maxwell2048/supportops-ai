# S11: Ticket forms and safe write recovery

Date: 2026-10-27 (Australia/Perth). [Execution evidence](evidence/2026-10-27-ticket-forms.md).

## Available operations

Requesters can create tickets, send public replies, and reopen resolved tickets with a public reason. Creation uses the signed-in identity/contact email; it cannot supply requester IDs or roles. The existing model does not have a phone field; this stage does not invent an unpersisted contact field.

Authorized agents and managers can send public replies/internal notes and perform allowed status transitions. Waiting for a customer or resolving requires a public reply in the same PATCH transaction. Managers can change assignment/priority, close resolved tickets, reopen closed tickets with a public reason, and archive/unarchive closed tickets. Archived tickets allow only manager unarchive. Ordinary messages do not automatically change status.

Action choices reflect current role/state for usability. The existing API independently checks current identity, object scope, role, version, target availability, and transition rules. The form supports one action at a time; managers assign an active agent before starting an unassigned ticket. The server's combined assignment/status capability remains available through the API.

GET /api/agents is manager-only, returns active agents ordered by email/id, and projects only id/email/role. It is not a general people directory and has no pagination for this small synthetic workspace. Refreshing checks availability again; the write service also locks/rechecks the selected agent. A removed selection remains explicitly unavailable instead of silently appearing unassigned. Submission stays disabled until a valid selection is chosen.

## Draft and retry rules

- Drafts, versions, attempt keys and exact submitted bodies stay in memory. The detail page owns draft state above the query loading/error boundary, so revalidation can remove private content from the DOM without losing input. Leaving that route, reloading, signing out or expiry discards drafts; this limitation is stated beside the forms.
- The first edit captures the displayed ticket version. A later refetch never silently rebases that draft. A 409 retains text/selection, reloads current data, and blocks submission until the user explicitly chooses the reviewed version. This creates a new attempt key and still requires a separate submit. Another intervening change can produce another 409.
- Every effective write uses a cryptographically generated UUID Idempotency-Key. Unchanged retries reuse the key/body; changing the operation, payload or reviewed version creates a new key. Successful operations clear the attempt.
- Transport errors, 5xx, or malformed success responses leave the outcome uncertain. Editing locks until the same request is retried. Ticket writes retain the exact original submitted body even if a background refresh changes current status/version. A successful replay is followed by a fresh authorized read rather than displaying an old cached write response as current truth.
- A synchronous ref guard and disabled submit controls prevent rapid double submissions. Mutations never automatically retry or queue for reconnection. Cancelling a browser request does not prove server rollback; leaving the page can lose an uncertain attempt key, so users should resolve uncertain results before navigating away.
- Success invalidates current-session lists/details. A 403/404/409 also triggers revalidation to remove stale access or obtain current state. A mutation 401 uses the same session-expiry path as protected reads. Unmount aborts the owned request and suppresses late navigation/state effects.
- Local labels, required fields, text limits and public/internal explanations accompany native controls. Safe known error codes provide actionable messages; arbitrary server/proxy text is never reflected. Status is expressed in text as well as color. Successful business writes are not shown optimistically.

## Verification boundaries

Backend tests exercise real PostgreSQL authorization/transactions. Node tests exercise typed write protocols, key reuse, public transition payloads, state choices and mutation expiry. Actual browser checks include keyboard submission, concurrent reply/assignment conflicts, unavailable targets, double clicks, lost acknowledgements, and a measured 390x844 assignment form. These checks do not establish a complete accessibility audit, cross-browser coverage or a persisted component/E2E suite; those remain S12.

The isolated browser helper accepts --lose-first-write-response and --write-delay-ms 0..2000. The former replaces only the first successful HTTP ticket write response with a synthetic 503 after the real API has committed. These switches exist only in the disposable loopback test helper, never production configuration. The test transport does not generate a normal API request ID for its replacement response; the underlying API request log records its original successful status.

This stage changes no database schema or dependency versions. Knowledge, AI, audit UI, phone persistence, production hosting, and remote CI validation remain outside this stage.
