# S06: Authentication and read authorization

S06 was locally verified with 73 tests; [evidence](evidence/2026-10-21-auth-verification.md). S07 reached 155 and S08 173 tests. See [tickets](tickets.md) and [audit](audit.md).

| Endpoint | Behavior |
|---|---|
| POST /api/auth/login | JSON email/password; short-lived Bearer token |
| GET /api/me | Current active id/email/role; no password hash |
| GET /api/tickets/{id} | Requester owns / agent currently assigned / manager all |
| GET /api/tickets/{id}/events | Authorized agent/manager; requester 403 |

Requester details query only public messages and omit events entirely. S07 writes recheck permissions transactionally. Login UI, registration, role editing, refresh tokens, and OIDC are not implemented.

## First local setup

Start PostgreSQL, apply migrations, and seed as described in [database setup](database.md). From backend:

```powershell
uv sync --locked
uv run --locked python ../scripts/configure_local_auth.py
uv run --locked python ../scripts/activate_demo_accounts.py
uv run --locked uvicorn supportops.main:app --app-dir src --host 127.0.0.1 --port 8000 --no-proxy-headers --no-access-log
```

configure_local_auth fills only missing/blank JWT_SECRET and DEMO_PASSWORD; it never prints or replaces existing values. Activation accepts only known synthetic IDs with matching email/role and the original disabled sentinel. It does not reset credentials or reactivate later-disabled accounts. Ordinary seeding also preserves existing state.

| Email | Role |
|---|---|
| requester-a@example.invalid / requester-b@example.invalid | requester |
| agent-a@example.invalid / agent-b@example.invalid | agent |
| manager@example.invalid | manager |

The five demo accounts use DEMO_PASSWORD from ignored .env for fictional local demonstrations only. Each stores an independently salted Argon2id hash. Never put credentials in command arguments, README, frontend, or Git. Port 8000 is occupied locally; checks used 8765. Match the Vite proxy when connecting business pages.

## Security parameters

- pwdlib[argon2] 0.3.1 and PyJWT 2.15.1, fixed HS256.
- JWT_SECRET: at least 32 bytes; local generator uses secrets.token_urlsafe(48). Settings repr hides DSN/secret. Missing secret means login/readiness 503.
- Default lifetime 15 minutes, configurable 1-30. Issuer supportops-api; audience supportops-web.
- Require/validate sub,jti,iss,aud,iat,nbf,exp; sub must be UUID; do not select algorithms from untrusted headers. Tokens contain no password, email, or role.
- Every protected request reloads active, role, and ownership. Disabling, role changes, and reassignment affect subsequent requests.
- Unknown email, incorrect password, and inactive account share a generic 401. Dummy password verification reduces obvious fast-path differences; this is not a constant-time claim.
- Future clients keep tokens in memory and reauthenticate after expiry. Clearing a token client-side does not revoke it server-side. There is no refresh/per-token revocation list; disabling accounts or rotating signing secrets invalidates relevant access.
- JWT signing does not encrypt contents. External TLS and cloud identity are later work.

## Errors and throttling

401 invalid session; 403 prohibited feature; 404 invisible/missing object; 422 invalid fields; 429 throttling; 503 database/auth configuration. Editing ticket IDs, token role claims, or submitted roles does not broaden scope.

Responses use server-generated X-Request-ID and API no-store. Unified errors never reflect passwords or request bodies. S08 adds transactional success audit, manager queries, and JSON failure tracing; failure logs are not persistent yet.

Throttle all attempts, including successes: 10/email/minute, 30/source-IP/minute, Retry-After:60. Email labels are SHA-256 hashes; at most 4096 buckets. Do not trust X-Forwarded-For; run locally with --no-proxy-headers. State is process-local and resets on restart. Shared throttling and trusted-proxy verification are required before multi-replica cloud deployment.

## Checks

```powershell
# backend; database running
uv run --locked python ../scripts/test_backend.py -q
# Start the API separately and adjust its port.
uv run --locked python ../scripts/check_auth.py --base-url http://127.0.0.1:8765
```

check_auth sends demo credentials only to localhost and prints neither passwords nor tokens. References: [FastAPI security](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/), [PyJWT API](https://pyjwt.readthedocs.io/en/stable/api.html), [pwdlib](https://frankie567.github.io/pwdlib/guide/).
