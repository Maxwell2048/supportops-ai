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

## Review and knowledge (planned)

- Suggestions: pending -> accepted / edited / rejected; terminal decisions cannot change again.
- Accepted/edited creates exactly one public message and updates reviewer, ticket version, and audit atomically. Rejected creates no public message. Evidence-free results may only be rejected; humans reply independently.
- Closed/archived tickets cannot publish suggestions. Changed ticket or knowledge content requires reanalysis: 409/stale_suggestion.
- Knowledge versions: draft -> published -> archived. Published content is immutable; edits create a new draft. Publishing atomically archives the old published version while preserving citation snapshots.
- Historical snapshots still require current permissions; publication requires sources to remain currently published and visible.
