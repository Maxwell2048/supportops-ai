# Read-only MCP server verification

Implemented: `backend/src/supportops/mcp_server.py` (low-level MCP `Server`, stateless Streamable HTTP at `/mcp`, `AccessTokenVerifier` over the API's `decode_subject`, four allow-listed read tools, per-call transaction with user reload and audit), migration `0011_mcp_tool_calls` and the `McpToolCall` model, `mcp==2.3.0` in `backend/pyproject.toml` and `uv.lock`, unit tests in `backend/tests/test_mcp_server.py` and PostgreSQL tests in `backend/tests/integration/test_mcp.py`. See [design](../mcp.md) and [ADR 0012](../adr/0012-read-only-mcp-server.md).

Environment on 2026-11-25: Windows, Python 3.14.7, uv 0.12.10, PostgreSQL 17.11 in the existing local development container (started for this session with the repository's Docker helper), branch based on `origin/main` at `ed22d44`.

## Automated checks

All tests that talk MCP go through the SDK's own client (`mcp.Client` with `streamable_http_client`) over an in-process ASGI transport, so JSON-RPC framing, protocol negotiation, the SDK bearer middleware and transport security are exercised, not only the handler functions. The integration tests use real PostgreSQL in an isolated migrated schema.

- `cd backend; uv run --locked python ../scripts/test_backend.py -q -p no:cacheprovider` (local `.env` loaded in-process; the helper sets `TEST_DATABASE_URL` to the dedicated `_test` database): **421 passed, 0 skipped** in 29.38 s. This includes the 20 PostgreSQL tool-loop cases under both orchestrations and the LangGraph backstop case that the [LangGraph evidence](2026-11-25-langgraph-tool-loop.md) recorded as not executed.
- The 40 new MCP tests alone, same command with the two files and `-v`: **40 passed** (32 unit, 8 PostgreSQL integration).
- `cd backend; uv run pytest -q` without a database URL: **145 passed, 276 skipped**. Every skip reports "Set TEST_DATABASE_URL to a dedicated PostgreSQL test database".
- `python scripts/check_repository_language.py`: "Language character check passed: 287 files, 0 commits, 0 historical blobs."

### What the 32 unit tests cover (database session replaced by a fake)

- `tools/list` under both negotiated protocol versions (`2026-07-28` with the default client, `2025-11-25` with `mode="legacy"`) returns exactly the four allow-listed tools, each with `additionalProperties: false`, bounded integer limits, a 500-character query limit, required `ticket_id` where applicable, read-only and non-destructive annotations, an output schema and the untrusted-content note. Listing opened no database session.
- Nine token cases (missing, malformed, Basic scheme, empty bearer, wrong signature, expired, wrong audience, wrong issuer, missing `jti`) get HTTP 401 with `WWW-Authenticate: Bearer` before JSON-RPC handling, without echoing the token and without opening a database session. The SDK client cannot connect with an invalid token. The verifier keeps only a 64-character digest of the token.
- Twelve invalid-argument cases return `invalid_arguments` with `field:error_type` details only; a marker string placed in values and in an extra key name never appears in the response, and the audit row has no ticket ID or result IDs.
- An unknown tool (`update_ticket`) is refused as `unknown_tool` and audited as `unknown`, without its name in the response.
- A requester, an inactive user and a valid token for a nonexistent user are refused (`forbidden`, `invalid_session`, `invalid_session`) even with invalid arguments, so authorization runs first.
- An in-process connection without HTTP authentication is denied. A database error returns a generic `unavailable` result without SQL text and records nothing. The history tool is the analysis tool's `_history` function.

### What the 8 PostgreSQL integration tests cover

- Agent A lists and reads their ticket (the body matches the database, and no requester ID, email or phone is returned) but gets `not_found` for agent B's ticket, for a random UUID and for agent B's ticket history. The three refusals are identical to each other and equal in code and message to the REST `GET /api/tickets/{id}` 404 for the same caller and ticket. A manager can read agent B's ticket.
- A requester who can read their own ticket through REST (HTTP 200) is refused for all four tools; four `forbidden` audit rows have role `requester` and no ticket ID.
- Within one MCP client connection: after reassignment the next `get_ticket` is `not_found`; after deactivation the next call is `invalid_session`. A manager downgraded to requester mid-connection is `forbidden` on the next call.
- `ticket_history` for an agent and a manager returns a new public message and never a new internal note, with message rows limited to `kind`, `from`, `created_at` and `body`, and no email address or user ID in the result.
- `search_knowledge` for an agent finds support knowledge but no management-scope passage, while a manager finds the management passage; `index_complete` is true.
- Seven mixed calls write seven audit rows in order with the expected tools, outcomes, actor, requested ticket IDs, returned ticket and chunk IDs and counts; each response's `request_id` matches its row; a marker placed in query text, extra arguments and an unknown tool name appears nowhere in the stored rows.
- When the audit insert is forced to violate its check constraint, the call returns `unavailable` without ticket text and no row exists, so no unaudited result is returned.

## Real process check

A scratch script started `uvicorn supportops.mcp_server:create_mcp_app --factory` as a separate process on `127.0.0.1:8791` with a throwaway random `JWT_SECRET` and no database configured, then used the SDK client over a real socket:

```text
no token: 401
foreign Host header: 421
protocol: 2026-07-28
tools: ['get_ticket', 'list_my_tickets', 'search_knowledge', 'ticket_history']
call without database: True unavailable
server log lines: 5 | contains secret: False
```

This shows the factory entry point, loopback Host checking and tool listing in a real process. It did not read data: the development database was not migrated to 0011 for this change, so no real-process call touched PostgreSQL.

## Not verified

- No real MCP client application (Claude Desktop or Claude Code) was connected; the configuration examples in the guide are unexercised.
- The development database was not upgraded to `0011_mcp_tool_calls`; migrations ran only in isolated test schemas.
- No remote CI ran for this change, and the Compose stack restore check (which now also fingerprints `mcp_tool_calls`) was not run. No frontend file changed, so the frontend was not rebuilt.
- No model was run against the tools, so prompt-injection resistance of any client model is not evaluated.
