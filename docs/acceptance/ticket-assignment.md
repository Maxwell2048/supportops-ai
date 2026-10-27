# Ticket assignment: Acceptance and implementation sequence

Date: 2026-10-22. S07 backend rules are verified: [evidence](../evidence/2026-10-21-ticket-workflow.md). S08 verifies A01 success audit and A06 audit-failure rollback: [evidence](../evidence/2026-10-22-audit-verification.md). S11 newly verifies A05 client assignment-selection preservation and explicit review, plus unavailable-target prompts in the real browser: [2026-10-27 evidence](../evidence/2026-10-27-ticket-forms.md).

Story: As a manager, I want to assign a ticket to an available support agent so responsibility and handoff history are explicit.

| ID | Given/when | Then | Stage |
|---|---|---|---|
| A01 | Valid manager, current version, non-archived ticket, active agent | Assignee changes; version+1/updated_at; one assignment event and success audit | S06-S08 |
| A02 | Non-manager tries assignment | 403; assignee/version/events unchanged | S06-S07 |
| A03 | Missing/inactive/non-agent target | 422 unavailable-assignee prompt; no partial change or success record | S07 |
| A04 | Target disabled after page loaded | Server locks/checks current target transactionally and rejects; old UI list is not trusted | S07 |
| A05 | Stale expected_version | 409; refresh/confirm prompt; client retains unsubmitted selection, without overwriting current state | S07/M2 |
| A06 | Event/audit insertion fails after assignment update | Full rollback restores assignee/version | S07-S08 |
| A07 | Matching identity/resource/operation/key/payload arrives again | Original result; no extra version/event/audit | S07-S08 |
| A08 | Same key, different payload | 409; no modification | S07 |
| A09 | Reassign archived ticket | 409; manager must unarchive first | S07 |
| A10 | Clear assignee while in_progress/waiting_customer | 409; keep assignee | S07 |
| A11 | Former agent accesses details/child resources after transfer | 404 under current assignment; new agent can read | S06-S07 |
| A12 | Same assignee and no other change | 422/no_changes; no version/success event | S07 |

Database constraints guarantee local invariants such as FKs, nullability, and enums. Roles, active state, authorization, transitions, idempotency, and audit require business transactions. Future target-disabling services must obey the same locking protocol.

S07 covers A01 business/event, A02-A04, server-side A05, event-failure A06, and A07-A12. Independent-connection tests cover disabling races and stale actor snapshots. Test-only account mutations do not imply an account-management API exists.

## Learning order

1. models.py represents current state and separate event history.
2. Immutable 0001 creates structures on a real empty database without importing changing models.
3. Constraint/rollback tests reject bad data and partial writes; this alone does not satisfy all acceptance criteria.
4. S06 adds trusted identity/authorization; S07 protected assignment; S08 transactional audit.
5. M2 adds conflict prompts, preserved input, and available-agent selection.

Question: why does a valid user FK not prove that the person can be assigned a ticket? Consider inactive accounts and requester roles.
