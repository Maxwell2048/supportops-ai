# MCP server: read-only support tools

SupportOps exposes four read-only support tools to external Model Context Protocol (MCP) clients, such as Claude Code or Claude Desktop. The client, and the model behind it, only proposes tool calls. The server decides, with the same role and object rules as the REST API. Implementation: `backend/src/supportops/mcp_server.py`. Decision record: [ADR 0012](adr/0012-read-only-mcp-server.md). Execution evidence: [2026-11-25 MCP evidence](evidence/2026-11-25-mcp-server.md).

## What is exposed

| Tool | Arguments | Returns | Authorization |
|---|---|---|---|
| `list_my_tickets` | `status` (optional ticket status), `limit` (1-20, default 10) | Ticket summaries (ID, title, status, priority, assignee ID, version, archived, timestamps) and `has_more` | The REST list query (`list_tickets`, `scoped_tickets`): agents see tickets assigned to them, managers see all |
| `get_ticket` | `ticket_id` (UUID) | One ticket: the summary fields plus `body` | `visible_ticket`, as `GET /api/tickets/{id}` |
| `ticket_history` | `ticket_id` (UUID), `limit` (1-10, default 10) | Public messages, each marked as from the requester or staff (body cut at 1,000 characters), and status event types | `visible_ticket`, then the analysis tool's own `_history` rule |
| `search_knowledge` | `query` (1-500 characters), `limit` (1-10, default 5) | Passages (article, version and chunk IDs, title, text, score) and `index_complete` | The scoped keyword `retrieval.search`: agents read current support knowledge, managers also management knowledge |

Every input schema is strict: `additionalProperties` is `false`, integers are bounded, and no type coercion happens (`"5"` is not `5`, `true` is not `1`). Every tool is annotated as read-only, non-destructive, idempotent and closed-world, and has an output schema. Successful results return the data as `structuredContent` and the same JSON as text content for clients that only read text.

Deliberately not exposed: internal notes, author user IDs, requester identity, account email and contact phone, analysis jobs and drafts, audit records, and anything that writes. The REST staff detail view shows some of these to staff; an external model does not need them.

## Running it

The MCP server is its own process, separate from the REST API. It uses the same `.env` configuration (database, `JWT_SECRET`, issuer, audience) and the same database, and its readiness depends on migration `0011_mcp_tool_calls`.

```powershell
Set-Location backend
uv run --locked alembic upgrade head
uv run --locked uvicorn supportops.mcp_server:create_mcp_app --factory --app-dir src --host 127.0.0.1 --port 8001 --no-proxy-headers --no-access-log
```

The endpoint is `http://127.0.0.1:8001/mcp` (Streamable HTTP, stateless, JSON responses). Host and Origin headers are restricted to loopback addresses to block DNS rebinding. There is no stdio transport: a stdio server would run as one fixed identity chosen at launch instead of authenticating each request.

## Authentication and authorization

1. **Bearer token.** The client sends the existing access JWT from `POST /api/auth/login` as `Authorization: Bearer <token>`. The MCP SDK's bearer middleware calls `AccessTokenVerifier`, which uses the API's own `decode_subject`: HS256 only, issuer, audience, expiry, not-before and all required claims. A missing, malformed, expired or foreign token gets HTTP 401 with `WWW-Authenticate: Bearer` before any JSON-RPC message is parsed. Only a SHA-256 digest of the token stays in the request scope.
2. **Per-call user reload.** Every `tools/call` opens its own short transaction and reloads the user. An unknown or inactive user gets `invalid_session`; a requester gets `forbidden`. This happens before the tool name or arguments are examined, so an unauthorized caller learns nothing about argument validity. Deactivation, a role change or a reassignment takes effect on the next call, even with a still-valid token.
3. **Allow-list and strict arguments.** An unknown tool name gets `unknown_tool`. Invalid arguments get `invalid_arguments` with details of the form `field:error_type`, for example `limit:less_than_equal`; an unknown field is reported as `<extra>:extra_forbidden`, so neither values nor client-chosen key names are echoed.
4. **Object authorization.** Reads go through the same functions as the REST API. A ticket outside the caller's scope returns `not_found` with the API's own message, identical to a ticket that does not exist, so the response does not reveal existence.
5. **Audit.** Each call writes one `mcp_tool_calls` row in the same transaction: request ID, actor and role snapshot, tool (`unknown` for names outside the allow-list), outcome, the requested ticket ID, returned object IDs (ticket or chunk IDs, at most 20) and a result count. Argument values, query text and tool names outside the allow-list are never stored. A result is returned only after that transaction commits, so there is no unaudited read. Requests refused at HTTP 401 have no actor and are not recorded; a database failure returns a generic `unavailable` error and records nothing.

Errors use the REST error envelope inside an `isError` tool result: `{"error": {"code", "message", "request_id", "details"}}`. Each success result also carries the `request_id` of its audit row.

`tools/list` needs a valid token but reads no database and returns the same fixed list to every caller.

## Example client configuration

Get an access token for an active synthetic agent or manager account (credentials live only in the ignored local `.env`):

```powershell
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/auth/login -ContentType application/json -Body (@{ email = '<agent email>'; password = '<password>' } | ConvertTo-Json)
$env:SUPPORTOPS_ACCESS_TOKEN = $login.access_token
```

Claude Code, from a terminal where that variable is set:

```powershell
claude mcp add --transport http supportops http://127.0.0.1:8001/mcp --header "Authorization: Bearer <ACCESS_TOKEN>"
```

Or a project `.mcp.json`:

```json
{
  "mcpServers": {
    "supportops": {
      "type": "http",
      "url": "http://127.0.0.1:8001/mcp",
      "headers": { "Authorization": "Bearer ${SUPPORTOPS_ACCESS_TOKEN}" }
    }
  }
}
```

Replace `<ACCESS_TOKEN>` with a real token only in local, uncommitted configuration. Tokens expire after `ACCESS_TOKEN_MINUTES` (15 by default, at most 30); there is no refresh, so the client must be given a new token. These configurations have not been exercised with a real Claude client; see the evidence for what ran.

## Threat notes

- **Prompt injection through tool results.** Ticket titles, bodies, public messages and knowledge passages are written by customers and knowledge authors. They are returned only as structured data fields, never placed in tool descriptions or server instructions, and every tool description and the server instructions say that these fields are untrusted data, not instructions. The client's model can still be influenced by them; the damage is bounded because every tool is read-only and scoped to the caller, and there is no write tool to steer.
- **Confused deputy.** The server never acts with more authority than the caller. It does not use a service account or a privileged database role for reads; every call reloads the caller and uses the caller's own scope. Tool parameters are object IDs that are re-authorized on each call, not capabilities.
- **No token passthrough.** The bearer token is verified and then reduced to its subject. No tool calls another service, so the token is never forwarded, and the raw token is not stored, logged or returned. The server accepts only tokens issued for this API's issuer and audience.
- **Least privilege.** Four read tools, staff only, bounded limits, minimized fields (no emails, phone numbers, internal notes or author IDs), keyword retrieval only (no outbound embedding calls), loopback-only Host and Origin checks, and a stateless transport with no server-side MCP session to hijack.
- **Token exposure on the client side.** An access token placed in a client configuration is a credential for the REST API too. Keep it in an environment variable or uncommitted configuration and prefer short expiry.

## Limits

- One process, loopback only. Exposing it beyond the machine would need TLS, a reviewed Host and Origin list, rate limiting and an OAuth 2.1 authorization server with protected-resource metadata instead of copying API tokens.
- `mcp_tool_calls` has no read API yet; inspect it with SQL.
- There are no write tools. ADR 0012 describes what one would need.
