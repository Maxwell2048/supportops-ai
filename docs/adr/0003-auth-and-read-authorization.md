# ADR 0003: Passwords, short-lived tokens, and current authorization

Date: 2026-10-21. Status: accepted; locally verified.

- Use pwdlib/Argon2id and PyJWT/HS256; do not implement hashing or signing. JSON login plus HTTPBearer is not an OAuth authorization server or OIDC implementation.
- Tokens express identity, timing, issuer, audience, and jti. Read current active, role, and object scope from the database on every request; never trust a role snapshot.
- Invalid sessions: 401; prohibited features: 403; invisible objects: 404. SQL filters public messages; requester schemas omit events.
- S06 exposes read-only details/events to verify object authorization. Writes/transactions/idempotency belong to S07 and full audit to S08.
- Explicit local scripts activate fictional accounts without changing seed idempotency. No registration/role-editing API. Secrets and passwords stay in ignored .env.
- Bounded single-process throttling fits local scope. Shared cloud throttling is later; do not add Redis prematurely.
- Unified errors and request IDs prevent credential reflection. Do not log full requests or Authorization.

Tradeoff: per-request database reads cost queries but apply current permissions promptly. There is no per-jti revocation list; short lifetimes and account-state checks are the initial control. Refresh tokens, key rotation, and cloud identity need separate design/verification.

See [authentication evidence](../evidence/2026-10-21-auth-verification.md).
