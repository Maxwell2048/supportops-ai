# S06 authentication and read-authorization acceptance

Date: 2026-10-21 (Australia/Perth). S06 authentication/read scope verified; not S07 writes, S08 audit, or M2 frontend.

## Delivery and execution

Pinned PyPI-verified pwdlib[argon2] 0.3.1 and PyJWT 2.15.1, updated uv.lock. Implemented login/me/ticket detail/events,15-minute fixed-HS256 JWTs with required claims/issuer/audience, current database active/role/scope, requester public-message-only schemas, bounded process-local throttling, safe errors/request IDs/no-store, local config/activation/HTTP helpers. Credentials only in ignored .env.

| Operation | Result |
|---|---|
| docker compose up -d --wait --wait-timeout 60 db | Existing container healthy; revision0001; five accounts preserved |
| backend: uv lock / uv sync --locked |38 packages resolved including project |
| backend: uv run --locked python ../scripts/test_backend.py -q | **73 passed in 2.63s,0 skipped** |
| backend: uv lock --check | Passed |
| configure_local_auth.py | Missing secret/demo password generated; no credential output |
| activate_demo_accounts.py twice | Activated5 then0; existing password/role preserved |
| check_auth.py --base-url http://127.0.0.1:8765 | Real HTTP passed; no password/JWT output |

## Tests

Existing DB cases plus Argon2 salts/wrong passwords; expired JWTs/wrong algorithms/signatures/issuer/audience/future iat-nbf/missing claims/invalid sub; generic unknown/inactive login; old tokens after disable; current role/reassignment; injected token roles; three-role object scopes; internal message/events exclusion; extra login fields; credential validation redaction; throttling and spoofed forwarded headers; repeat activation preserving passwords/later disabled status.

Integration tests used supportops_test random schemas. Test-fixture account mutations validated reads and did not imply production write APIs existed.

## Real HTTP

Temporary127.0.0.1:8765 API with --no-proxy-headers:

- Five demo logins200; me matched id/email/role.
- Requester-a own ticket200, no events; requester-b same ticket404.
- Requester events403; manager events200.
- Unauthenticated me401; ready200.

After activation:5 accounts,1 ticket,1 event. No create/assign/reply occurred and login did not change roles. Temporary API stopped; development DB stayed running; existing8000 process untouched. Aggregate check: all 5 active with Argon2id prefixes (boolean only, no hashes), random schemas0. Python syntax, local Markdown links, git diff --check passed;8765 closed.

## Limits

Readiness needs auth config and migrated DB. No login frontend, refresh/per-token revocation, registration/role edits, or OIDC. Throttles do not persist/share across restarts/replicas; cloud needs shared control and proxy verification. No new tables or historical migration edits. Audit/logging/writes/idempotency followed later. Remote CI unverified; unchanged frontend not rebuilt in this stage.
