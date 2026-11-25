# ADR 0012: Expose read-only support tools over MCP with the API's own authorization

Status: accepted on 2026-11-25.

## Context

External agent clients such as Claude Code and Claude Desktop speak the Model Context Protocol (MCP). I wanted staff to be able to look up their tickets and support knowledge from such a client without opening a second, weaker path into the data. The existing analysis tool loop ([ADR 0011](0011-controlled-read-only-tool-use.md)) already established the rule this server must keep: the model proposes, the server decides, and the decision uses the same role and object checks as the REST API.

## Decision

- **SDK and server style.** I used the official MCP Python SDK, pinned as `mcp==2.3.0` (current on PyPI at the time; it serves both the 2026-07-28 protocol and the 2025-11-25 handshake). I used the low-level `Server` with explicit `tools/list` and `tools/call` handlers rather than the decorator-based `MCPServer`. The high-level server derives schemas from function signatures and produces its own validation errors; I need exact control over the input schemas (strict Pydantic models with forbidden extra fields and bounded limits), over the order of checks, and over error text, so that rejections never echo argument values.
- **Transport.** Streamable HTTP at `/mcp`, stateless, with JSON responses. Stateless mode means there is no server-side MCP session that could be hijacked, expire or carry stale authorization; every HTTP request is authenticated on its own and every tool call re-authorizes. Host and Origin headers are restricted to loopback addresses to prevent DNS rebinding. I did not add stdio: a stdio server runs as one identity fixed at launch and has no per-request credential, which would weaken the per-call identity model.
- **Separate entry point, not mounted on the REST app.** `supportops.mcp_server:create_mcp_app` is its own ASGI application, run as its own process on port 8001. Reasons: it can be left off where it is not wanted, which is the least-privilege default; it owns its own lifespan (the SDK session manager) and transport security without changing the REST app's middleware, error handlers or request logging; and a defect in the MCP layer cannot change REST behavior. Reuse happens at the code level, not by calling the REST API over HTTP: the same `decode_subject`, `visible_ticket`, `list_tickets` and `retrieval.search` functions and the same database. The cost is one more process to run.
- **Authentication.** The bearer token is the existing access JWT, verified through the SDK's bearer middleware by a `TokenVerifier` that calls the API's `decode_subject` (signature, issuer, audience, expiry, required claims). Invalid tokens get HTTP 401 before JSON-RPC parsing. The verifier does not touch the database; instead, every tool call opens its own short transaction that reloads the user and requires an active agent or manager before looking at the tool name or arguments. A still-valid token therefore stops working on the next call after deactivation or a role change. The raw token is reduced to its subject and a digest, never stored, logged or forwarded.
- **Requesters are denied.** Requesters can read their own tickets through the REST API, but nothing they need requires an external agent client, and the tools are designed for staff. Denying them keeps the exposed surface smaller.
- **Same refusals as the API.** A ticket outside the caller's scope returns the API's own `not_found` code and message, identical to a nonexistent ticket. Role and session refusals use the API's wording.
- **Separate audit table.** `audit_events` is constrained to successful ticket writes, unique per ticket version, so it cannot record reads or refusals. Migration `0011_mcp_tool_calls` adds a table that records request ID, actor and role snapshot, tool (`unknown` outside the allow-list), outcome, the requested ticket ID (no foreign key, so probes for nonexistent IDs stay visible), returned object IDs and a count. It never records argument values, query text or unknown tool names. The audit row is written in the call's transaction, and the result is returned only after it commits.
- **Data minimization.** Tool results omit internal notes, author user IDs, requester identity, account email and contact phone. Ticket history reuses the analysis tool's `_history` function, so the public-only rule is one piece of code. Retrieval is keyword-only, so no MCP call causes an outbound embedding request.
- **Untrusted content.** Ticket and knowledge text appears only in structured result fields; tool descriptions and server instructions are fixed server text and state that those fields are untrusted data.

## No write tools yet

This change has no write tools. A future write tool, for example "draft a reply", would need at least:

1. **An idempotency key** in its arguments, stored through the existing `idempotency_records` claim and replay, so a client retry after a lost response cannot create a second effect.
2. **A draft-only effect.** It may create a suggestion or draft that enters the existing human review workflow, never a public reply, status change or closure.
3. **Human confirmation.** A staff member confirms in the SupportOps review workspace, not in the MCP client, because the client's model may be steered by injected ticket text. MCP elicitation inside the client is not sufficient on its own.
4. The same per-call reload and object checks as reads, the ticket version as an optimistic concurrency check, an audit row in the same transaction as the effect, and a per-actor rate limit.

## Alternatives considered

- **Mount on the FastAPI app.** Fewer processes, but the MCP endpoint would always be exposed with the API and would share middleware and lifespan. Rejected for the reasons above; it remains easy to add later because the factory returns a plain ASGI app.
- **`MCPServer` with decorated functions.** Less code, but less control over schemas and error text.
- **An MCP proxy that calls the REST API with the user's token.** This is token passthrough: the MCP layer would forward a credential and could be used as a confused deputy if it ever added its own authority. Rejected; calling the same functions in-process keeps one authorization path without forwarding anything.
- **OAuth 2.1 with protected-resource metadata.** The right model for a remotely reachable MCP server, but the project has no authorization server. For a loopback-only local delivery, reusing short-lived API tokens is simpler and honest about its limits.

## Consequences

Staff can use an MCP client to read exactly what the REST API would show them, minus sensitive fields. Each call costs one transaction with an audit insert. Tokens expire after at most 30 minutes and must be replaced by hand. The server is loopback-only; remote exposure needs TLS, OAuth, rate limiting and a reviewed Host and Origin list. Real-client behavior (Claude Desktop or Claude Code) is not yet verified.

References: [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), [MCP specification: authorization and security best practices](https://modelcontextprotocol.io/specification), [Pydantic strict mode](https://docs.pydantic.dev/latest/concepts/strict_mode/).
