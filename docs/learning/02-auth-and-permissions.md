# S06 code reading order

1. routes.py login: validate -> rate limit -> load user -> check password/active -> issue token.
2. security.py: delegate hashing/JWT to established libraries; fix algorithms and required claims.
3. dependencies.py get_current_user: trusted subject identifies the current database account; reread active/role.
4. visible_ticket: SQL limits requester_id/assignee_id; missing and unauthorized objects both return 404.
5. ticket_detail: requesters query public messages only and receive no events field.
6. tests/integration/test_auth.py: cross-user access, account disabling, reassignment, role changes, internal-field isolation.

Authentication answers who you are. Authorization decides whether this specific operation is allowed. A valid token does not let a requester read another person's ticket.

S06 passed 73 tests at that stage; see [evidence](../evidence/2026-10-21-auth-verification.md). S07 added writes, transitions, and idempotency (155 tests). S08 added transactional audit (173 tests). S09 now adds memory-only login and scoped read views; see [frontend guide](../frontend.md). See [ticket behavior](../tickets.md).
