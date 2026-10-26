# ADR 0006: Memory-only sessions and typed, cancellable frontend requests

Date: 2026-10-27. Status: accepted. [Evidence](../evidence/2026-10-27-frontend-foundation.md).

Problem: static pages cannot demonstrate authorized ticket reads, and naive async state can display data from a previous ticket/account or treat proxy failures as success.

Decision: build a small same-origin API client with explicit DTOs/runtime validation, a 15-second deadline, request cancellation, safe status messages, and UUID request IDs. Fetch with no-store, omit cookies, and reject redirects. Obtain current identity via /me rather than client token claims. Keep tokens only in memory; unmount the entire private workspace per session and discard superseded effect results.

Use hash routes and uncached reads for S09 instead of adding routing/cache libraries before their milestones. S10 introduces TanStack Query and its richer state/invalidation policy. Basic cursor navigation already prevents silently truncating long lists. Keep writes/AI actions out of this read-only increment.

Runtime DTO projection additionally excludes requester internal content, while real API authorization remains the security boundary. React renders bodies as text; raw server/proxy error messages and arbitrary event change objects are not inserted into the UI.

Tradeoffs: refresh requires login; sign-out does not revoke an issued JWT; no shared client cache, automatic retries, filters, or directory display names. DTO declarations must evolve with the API; runtime guards and protocol tests detect drift. Real manual browser checks use isolated synthetic PostgreSQL fixtures, not the development credential or a mock authorization path. Complete component/E2E automation remains S12.
