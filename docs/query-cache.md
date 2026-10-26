# S10: Query cache, filters, and pagination

Date: 2026-10-27. [Execution evidence](evidence/2026-10-27-query-cache.md).

## Ownership and freshness

TanStack React Query 5.105.0 is pinned with its lockfile. The npm registry declares React 18/19 support. Each successful sign-in creates a new QueryClient; logout, protected401, expiry, replacement sign-in, and application unmount clear it. There is no disk/browser-storage persistence or cross-tab cache sharing.

Keys use session nonce, account UUID, role, ticket resource, normalized filters, page cursor, and limit 20. JWTs and passwords never appear in keys. Different logins, roles, accounts, filters, cursors, and list/detail operations cannot share a key.

Configuration: staleTime 15 seconds, unused-query gcTime 120 seconds, no automatic retries, networkMode=always. Mount/focus/reconnect always revalidate. List pages remount on filter/cursor identity changes, so even a fresh cached previous page goes through mount revalidation. Detail pages remount per ticket. The view hides data while fetching or after errors; it does not present a previous successful cache value as current authorization.401 clears the entire session.403/404 and transport errors show safe feedback rather than old details.

This deliberately prioritizes current server authorization over instant cached navigation. Cache retention supports deduplication, query lifecycle, and invalidation; it does not establish offline access, realtime permission revocation without a request, or measured speedups. Server object authorization remains authoritative. Role labels come from login identity; backend scope is checked again for every fetch.

Refresh invalidates all ticket list/detail keys for the current session and refetches active observers. The same helper is available for S11 successful writes. No optimistic writes or background mutation queue exists. Inactive variants remain invalidated until revisited.15/120-second values are explicit local policy choices, not measured performance results.

## Filters and navigation

- Search covers original title/body via the existing server API, never internal notes. Whitespace is trimmed; maximum 200 characters. Status/priority use fixed enums. Parameters use URLSearchParams, preserving literal percent/underscore/reserved characters.
- Applied q/status/priority live in the hash URL. Draft input is separate and applies only on submit. Clear resets all filters. Do not put sensitive information in shareable search URLs; tokens are never encoded there.
- Applying filters starts at page 1. Each page uses the server's signed keyset cursor; next/previous track cursor history in session memory. Browser history between filter URLs restarts that filter's page 1.
- Entering a detail and using Back to tickets preserves the last filter URL and cursor position. Refreshing the browser loses the in-memory session/pager and requires login. There is no cross-request snapshot or global total.
- Expired/mismatched cursor errors offer Start from first page. Malformed filter addresses produce local422 feedback before any list request; the workspace link returns to a valid list.

## Repeat verification

```powershell
# frontend, Vite stopped before clean install on Windows
npm ci
npm run build
npm run test:api
npm run test:query
# backend, separate terminal, after test database setup
uv run --locked python ../scripts/serve_frontend_check.py --extra-tickets 24 --session-minutes 10 --read-delay-ms 700
```

Use the same local proxy and public synthetic fixture password described in [frontend setup](frontend.md). Extra tickets belong to requester-a, alternating normal/high priority. The helper still defaults to zero extras and one-minute sessions for the original S09 checks. Ctrl+C removes only its owned random schema.

Tests use real QueryClient/QueryObserver behavior, not mocks of cache methods. A Node-only timeout provider unreferences query GC timers so completed tests exit normally; browser defaults and cleanup policy are unchanged. Full React component/Playwright automation is still S12.

References: [query keys](https://tanstack.com/query/latest/docs/framework/react/guides/query-keys), [cancellation](https://tanstack.com/query/latest/docs/framework/react/guides/query-cancellation), [defaults](https://tanstack.com/query/latest/docs/framework/react/guides/important-defaults).
