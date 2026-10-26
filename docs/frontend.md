# S09: Typed frontend and read-only business pages

Date: 2026-10-27 (Australia/Perth). [Verification evidence](evidence/2026-10-27-frontend-foundation.md).

## Scope

Implemented: email/password login, current identity, role-scoped ticket list, basic cursor next/previous navigation, ticket details, public/internal conversation, staff activity, explicit loading/empty/error/success views, refresh, sign-out, and expired-session handling. UI copy and source comments are English; timestamps explicitly use Perth (UTC+8).

This stage reads existing ticket APIs. Ticket creation/assignment/replies/state forms, knowledge/AI controls, manager audit UI, filters, TanStack Query caching, and the complete component/E2E suite are later milestones. No mock data is displayed as real application data.

## Run against the development database

Complete [database](database.md) and [authentication](auth.md) setup. From backend:

```powershell
uv run --locked uvicorn supportops.main:app --app-dir src --host 127.0.0.1 --port 8765 --no-proxy-headers --no-access-log
```

From frontend, in another PowerShell terminal:

```powershell
npm ci
$env:SUPPORTOPS_API_TARGET = 'http://127.0.0.1:8765'
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Vite defaults to API port 8000 unless SUPPORTOPS_API_TARGET is set. Its strict port 5173 avoids silently moving to another port. The proxy variable is server-side configuration, not a VITE-prefixed secret exposed to the browser. After stopping Vite, remove the temporary shell override with `Remove-Item Env:SUPPORTOPS_API_TARGET` if appropriate.

Use the assigned local account and password from ignored configuration. Do not put real/demo credentials in source, URLs, screenshots, or command-line arguments. The browser always calls relative /api routes; production needs an equivalent same-origin reverse proxy, delivered later with deployment/Compose.

On Windows, stop Vite before npm ci: its loaded native binding can prevent npm from replacing node_modules. Stopping the owned dev server and retrying was verified; no dependency upgrade was needed.

## Session and request boundaries

- Tokens live only in React memory; no localStorage, sessionStorage, cookies, or URL token persistence. Refreshing/closing the document loses the session. Sign-out removes client state; it is not server-side token revocation.
- Login gets a token, then /me establishes identity/role. Session deadlines use the login-request start and server TTL; a timer and any protected401 return to login. Server checks remain authoritative, including disabling/reassignment after login. Refresh/session renewal are not implemented.
- Each sign-in mounts a new workspace, even for the same account. Sign-out, expiry, account changes, route changes, and retries cancel superseded fetches; active-effect guards reject late results. A changed request key renders loading rather than a previous ticket.
- Requests have a 15-second deadline, omit ambient cookies, disable cache, and reject redirects. Unknown proxy/server error bodies are not reflected. Error cards show safe messages and validated UUID request IDs when available; network/proxy failures may have no API request ID.
- Explicit TypeScript DTOs have runtime field validation. Unknown fields are discarded. A requester projection drops internal messages/events as display defense; server role/object authorization remains mandatory and independently tested.
- Ticket text is rendered as React text, never injected HTML. Staff activity shows event metadata without copying arbitrary change objects. The current API returns participant/assignee IDs rather than a user directory. Staff views use those identifiers; requester views say Support team or Awaiting assignment instead of exposing personnel identifiers. The UI does not invent personal names.
- Hash routes support list/detail/back navigation without a routing dependency. Basic paging is uncached; returning from details starts the list at page 1. S10 adds query keys, filter state, cache invalidation, and richer pagination behavior.

## Repeatable browser fixture server

First prepare supportops_test using the normal backend test helper. Stop any owned API on 8765, then run from backend:

```powershell
uv run --locked python ../scripts/test_backend.py -q
uv run --locked python ../scripts/serve_frontend_check.py --read-delay-ms 1200
```

Run Vite with the 8765 proxy as above. The fixture server uses the actual FastAPI app, migrations, authorization, and real PostgreSQL in a random schema in the dedicated *_test database. It never substitutes mocked responses for the role checks.

The five existing synthetic account labels use the public test-only password `S09-local-synthetic-only!`. This value is explicitly disposable fixture data, not a local development credential. Sessions last one minute so expiry can be observed. Optional read delay0-2000ms exposes loading/race states; it exists only in this fixture helper.

- requester-a: one assigned ticket with one public reply; internal note/events excluded.
- agent-a: that ticket, public reply, internal note, and staff activity.
- manager: both requesters' tickets.
- requester-b: a separate ticket without replies.
- agent-b: no assignments; direct access to either ticket is denied.

Ctrl+C removes only the internally generated owned schema; this cleanup was verified. Abrupt process termination cannot guarantee finally cleanup, so use a dedicated test database. Do not run this public-password fixture server against development/production data or expose it beyond loopback.

## Checks and limits

```powershell
# frontend, with Vite stopped for clean installation
npm ci
npm run build
npm run test:api
```

The dependency-free Node API suite checks credentials/URL boundaries, DTO validation, requester projection, error redaction/status/request IDs, cursor encoding, cancellation, timeouts, and network failure. CI is configured to run it, but a configuration edit is not remote CI verification. There are no dependency/version changes in S09; lockfiles remain unchanged.

Actual browser checks are recorded separately from unit tests. S12 still owns a persisted Playwright/RTL regression suite and broad browser coverage. Desktop-wide, cross-browser, full keyboard/screen-reader, and WCAG conformance are not claimed from the narrow-view smoke check.
