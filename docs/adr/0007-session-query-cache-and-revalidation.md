# ADR0007: Session-owned caches with server revalidation

Date: 2026-10-27. Status: accepted, S10 locally verified.

Problem: uncached reads lack shared query lifecycle, filter isolation, and retained paging. A naive shared cache can display another account's or previously authorized data, especially after failed background refetches.

Decision: use pinned TanStack React Query 5.105.0 with a new client per login, identity/role/session-scoped keys, consumed AbortSignals, and explicit clearing at session boundaries. Maintain filters in hash URLs and cursor history in workspace memory. Remount list observers per filter/cursor key and detail observers per ID, always revalidating on mount/focus/reconnect. Hide cached values during revalidation and on errors. A common invalidation helper marks current-session ticket lists/details stale and refetches active queries.

Tradeoff: this is not instant offline cache navigation. Zero automatic retries avoid repeated forbidden requests and hide no failures; manual refresh is explicit.15-second freshness and 120-second inactive retention are conservative declared settings. Current server authorization outweighs unmeasured latency claims. Query keys contain no bearer token, and caches are never persisted.

The previous custom useRemote hook is removed instead of maintaining two server-state systems. Node tests verify actual query-core deduplication, invalidation, disposal, cancellation, fresh-cache mount revalidation, and failed-data suppression. Real browser pagination/filter/account checks complement them; S12 still delivers a persisted component/E2E suite. [Evidence](../evidence/2026-10-27-query-cache.md).
