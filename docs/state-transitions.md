# State transitions

Ticket rules are implemented in S07. AI and knowledge rules below remain designs.

## Tickets

Initial state: open, version 1. Unlisted transitions return 409/invalid_transition. Setting the existing status alone with no actual field change returns 422/no_changes.

| From | To | Role | Rule |
|---|---|---|---|
| open | in_progress | Current agent / manager | Active agent assigned; manager may assign in the same request |
| in_progress | waiting_customer | Current agent / manager | Public human reply in the same transaction |
| waiting_customer | in_progress | Current agent / manager | Current assignee is active |
| in_progress / waiting_customer | resolved | Current agent / manager | Required public_reply becomes a public resolution message |
| resolved | in_progress | Owning requester / current agent / manager | Required public reason; retain active assignee; no simultaneous reassignment |
| resolved | closed | Manager | Explicit manual close |
| closed | open | Manager | Required public reason; clear assignee; no simultaneous assignment |

Archive is a separate field set by managers only on closed tickets. Archived tickets accept only a standalone manager unarchive action before any reopening. Every write checks object authorization and expected_version. Reassignment does not implicitly change status. Tickets in_progress/waiting_customer cannot lose their assignee. Ordinary requester replies do not change status automatically.

The reason field is for reopening only; public_reply is for waiting_customer/resolved only. Other conversation uses messages. Managers may adjust assignee/priority on non-archived closed tickets, but ordinary messages remain prohibited. See [ticket rules](tickets.md).

## AI jobs (planned)

queued -> running -> succeeded / failed. An expired running lease returns to queued while attempts < 3, otherwise failed. Lease acquisition increments attempts atomically. Lease tokens protect renewal and final writes; stale workers cannot commit. Suggestion insertion and succeeded state share a transaction.

Retry temporary timeouts/service failures with backoff; revoked permissions, invalid configuration, and invalid citations are permanent failures. Missing evidence can be a successful handoff result and must not conceal provider failure. Timeout, lease, and backoff parameters are fixed and verified in S16.

## Review (planned)

- Suggestions: pending -> accepted / edited / rejected; terminal decisions cannot change again.
- Accepted/edited creates exactly one public message and updates reviewer, ticket version, and audit atomically. Rejected creates no public message. Evidence-free results may only be rejected; humans reply independently.
- Closed/archived tickets cannot publish suggestions. Changed ticket or knowledge content requires reanalysis: 409/stale_suggestion. A completed review retried with its original Idempotency-Key and body returns the stored receipt even if a cited source changed afterwards; current role and assignment are still checked first.

## Knowledge (S13 locally verified)

- Every save creates an immutable draft snapshot. Publishing selects one current version; superseded publications derive archived status without updating their stored content. Archiving the article removes current availability. Explicit manager publication may restore a historical snapshot.
- Article revision changes for each effective draft/publication/archive operation, independently of version numbers. Current revision and persistent idempotency protect writes; knowledge audit shares the transaction.
- Requesters cannot access knowledge. Historical agent reads require previous publication plus support scope on both the historical and current publication, and an active article. Draft/management/archived-article references are denied. Only the current pointer is eligible for future retrieval. [Full policy](knowledge.md).
- Future suggestion publication must also recheck that cited sources remain currently published and authorized; that review workflow remains S18/S19.
