"""MCP server unit tests over the real JSON-RPC layer; the database session is replaced by a fake."""
from contextlib import asynccontextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import anyio
import httpx2
import jwt
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy.exc import OperationalError

from supportops import mcp_server
from supportops.config import Settings
from supportops.security import issue_token

SECRET = "unit-only-mcp-signing-secret-value-" * 2
SETTINGS = Settings(jwt_secret=SECRET)
BASE = "http://127.0.0.1:8001"
ALLOWLIST = {"list_my_tickets", "get_ticket", "ticket_history", "search_knowledge"}
AGENT, MANAGER, REQUESTER, INACTIVE, MISSING = (uuid4() for _ in range(5))
USERS = {
    AGENT: SimpleNamespace(id=AGENT, role="agent", active=True),
    MANAGER: SimpleNamespace(id=MANAGER, role="manager", active=True),
    REQUESTER: SimpleNamespace(id=REQUESTER, role="requester", active=True),
    INACTIVE: SimpleNamespace(id=INACTIVE, role="agent", active=False),
}


class FakeSession:
    """Stands in for SQLAlchemy: user reload and audit rows, nothing else."""

    opened, added, fail = 0, [], None

    def __init__(self, engine):
        FakeSession.opened += 1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def begin(self):
        return nullcontext()

    def get(self, model, key):
        if FakeSession.fail:
            raise FakeSession.fail
        return USERS.get(key)

    def add(self, row):
        FakeSession.added.append(row)


@pytest.fixture(autouse=True)
def fake_database(monkeypatch):
    monkeypatch.setattr(mcp_server, "Session", FakeSession)
    FakeSession.opened, FakeSession.added, FakeSession.fail = 0, [], None
    return FakeSession


def token_for(user_id=AGENT, **claims):
    if not claims:
        return issue_token(user_id, SETTINGS)
    now = datetime.now(timezone.utc)
    body = {"sub": str(user_id), "jti": str(uuid4()), "iss": SETTINGS.jwt_issuer, "aud": SETTINGS.jwt_audience,
            "iat": now, "nbf": now, "exp": now + timedelta(minutes=5)}
    secret = claims.pop("secret", SECRET)
    body.update(claims)
    return jwt.encode({key: value for key, value in body.items() if value is not None}, secret, algorithm="HS256")


@asynccontextmanager
async def mcp_client(token, mode="auto"):
    app = mcp_server.create_mcp_app(SETTINGS, engine=object())
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with app.router.lifespan_context(app):
        async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=BASE, headers=headers) as http:
            async with Client(streamable_http_client(BASE + "/mcp", http_client=http), mode=mode) as client:
                yield client


def call(name, arguments, user_id=AGENT):
    async def scenario():
        async with mcp_client(token_for(user_id)) as client:
            return await client.call_tool(name, arguments)
    return anyio.run(scenario)


@pytest.mark.parametrize("mode", ["auto", "legacy"])
def test_list_tools_returns_exactly_the_read_only_allowlist_with_strict_schemas(mode):
    async def scenario():
        async with mcp_client(token_for(), mode) as client:
            return client.protocol_version, (await client.list_tools()).tools
    version, tools = anyio.run(scenario)
    assert version == ("2026-07-28" if mode == "auto" else "2025-11-25")
    assert {tool.name for tool in tools} == ALLOWLIST and len(tools) == len(ALLOWLIST)
    for tool in tools:
        schema = tool.input_schema
        assert schema["type"] == "object" and schema["additionalProperties"] is False
        assert tool.annotations.read_only_hint is True and tool.annotations.destructive_hint is False
        assert tool.annotations.open_world_hint is False
        assert "untrusted" in tool.description and tool.output_schema["type"] == "object"
        for field in schema["properties"].values():
            if field.get("type") == "integer":
                assert field["minimum"] == 1 and field["maximum"] <= 20
    schemas = {tool.name: tool.input_schema for tool in tools}
    assert schemas["list_my_tickets"]["properties"]["limit"]["maximum"] == 20
    assert schemas["ticket_history"]["required"] == ["ticket_id"]
    assert schemas["ticket_history"]["properties"]["limit"]["maximum"] == 10
    assert schemas["get_ticket"]["required"] == ["ticket_id"]
    assert schemas["search_knowledge"]["required"] == ["query"]
    assert schemas["search_knowledge"]["properties"]["query"]["maxLength"] == 500
    assert schemas["search_knowledge"]["properties"]["limit"]["maximum"] == 10
    # Listing tools needs a valid token but no database work.
    assert FakeSession.opened == 0


@pytest.mark.parametrize("header", [
    None, "Bearer not-a-jwt", "Basic dXNlcjpwYXNz", "Bearer ",
    "Bearer " + token_for(secret="another-signing-secret-of-enough-length!"),
    "Bearer " + token_for(exp=datetime.now(timezone.utc) - timedelta(seconds=5)),
    "Bearer " + token_for(aud="another-audience"),
    "Bearer " + token_for(iss="another-issuer"),
    "Bearer " + token_for(jti=None),
], ids=["missing", "malformed", "basic", "empty", "signature", "expired", "audience", "issuer", "no-jti"])
def test_missing_or_invalid_tokens_are_rejected_before_json_rpc(header):
    async def scenario():
        app = mcp_server.create_mcp_app(SETTINGS, engine=object())
        headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        if header:
            headers["Authorization"] = header
        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=BASE) as http:
                return await http.post("/mcp", headers=headers, json={
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                    "params": {"name": "list_my_tickets", "arguments": {}}})
    response = anyio.run(scenario)
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Bearer")
    assert response.json()["error"] == "invalid_token"
    if header and len(header) > 7:
        assert header[7:] not in response.text
    assert FakeSession.opened == 0


def test_sdk_client_cannot_connect_with_an_invalid_token():
    async def scenario():
        async with mcp_client("not-a-jwt") as client:
            await client.list_tools()
    with pytest.raises(BaseException):
        anyio.run(scenario)
    assert FakeSession.opened == 0


def test_verifier_keeps_only_a_digest_of_the_bearer_token():
    token = token_for()
    verified = anyio.run(mcp_server.AccessTokenVerifier(SETTINGS).verify_token, token)
    assert verified.subject == str(AGENT) and verified.token != token and len(verified.token) == 64
    assert token not in verified.model_dump_json()
    assert anyio.run(mcp_server.AccessTokenVerifier(Settings()).verify_token, token) is None


@pytest.mark.parametrize(("name", "arguments", "details"), [
    ("get_ticket", {"ticket_id": "SECRET-VALUE-not-a-uuid"}, ["ticket_id:uuid_parsing"]),
    ("get_ticket", {}, ["ticket_id:missing"]),
    ("list_my_tickets", {"limit": 21}, ["limit:less_than_equal"]),
    ("list_my_tickets", {"limit": 0}, ["limit:greater_than_equal"]),
    ("list_my_tickets", {"limit": "5"}, ["limit:int_type"]),
    ("list_my_tickets", {"status": "SECRET-VALUE"}, ["status:literal_error"]),
    ("ticket_history", {"ticket_id": str(uuid4()), "SECRET-KEY": "SECRET-VALUE"}, ["<extra>:extra_forbidden"]),
    ("ticket_history", {"ticket_id": str(uuid4()), "limit": 11}, ["limit:less_than_equal"]),
    ("search_knowledge", {"query": "SECRET-" + "x" * 500}, ["query:string_too_long"]),
    ("search_knowledge", {"query": "   "}, ["query:string_too_short"]),
    ("search_knowledge", {"query": "SECRET\x00VALUE"}, ["query:value_error"]),
    ("search_knowledge", {"query": "SECRET", "limit": True}, ["limit:int_type"]),
])
def test_invalid_arguments_are_rejected_without_echoing_their_values(name, arguments, details):
    result = call(name, arguments)
    assert result.is_error is True
    error = result.structured_content["error"]
    assert error["code"] == "invalid_arguments" and error["details"] == details
    assert error["message"] == "Invalid tool arguments"
    assert "SECRET" not in result.model_dump_json()
    (row,) = FakeSession.added
    assert (row.tool, row.outcome, row.actor_id, row.ticket_id, row.result_ids) == (name, "invalid_arguments", AGENT, None, [])


def test_unknown_tools_are_refused_and_audited_without_their_name():
    result = call("update_ticket", {"status": "closed"})
    assert result.is_error and result.structured_content["error"]["code"] == "unknown_tool"
    assert "update_ticket" not in result.model_dump_json()
    (row,) = FakeSession.added
    assert (row.tool, row.outcome) == ("unknown", "unknown_tool")


@pytest.mark.parametrize(("user_id", "code", "message"), [
    (REQUESTER, "forbidden", "Your current role cannot use this feature"),
    (INACTIVE, "invalid_session", "Your session is invalid; please sign in again"),
    (MISSING, "invalid_session", "Your session is invalid; please sign in again"),
])
def test_role_and_active_state_are_checked_before_arguments(user_id, code, message):
    # Arguments are invalid on purpose: an unauthorized caller must not learn even that.
    result = call("get_ticket", {"ticket_id": "SECRET"}, user_id)
    assert result.structured_content["error"]["code"] == code
    assert result.structured_content["error"]["message"] == message
    (row,) = FakeSession.added
    assert row.outcome == code and row.ticket_id is None
    assert row.actor_id == (None if user_id == MISSING else user_id)


def test_in_process_connection_without_http_authentication_is_denied():
    async def scenario():
        async with Client(mcp_server.build_server(object(), SETTINGS)) as client:
            return await client.call_tool("list_my_tickets", {})
    result = anyio.run(scenario)
    assert result.structured_content["error"]["code"] == "invalid_session"
    assert FakeSession.added[0].actor_id is None


def test_database_failure_returns_a_generic_error_without_audit_or_details():
    FakeSession.fail = OperationalError("SELECT secret_column FROM users WHERE token = 'SECRET'", {}, Exception("SECRET"))
    result = call("list_my_tickets", {})
    assert result.structured_content["error"]["code"] == "unavailable"
    assert "SECRET" not in result.model_dump_json() and "secret_column" not in result.model_dump_json()
    assert FakeSession.added == []


def test_history_tool_reuses_the_analysis_history_rule():
    from supportops import agent_tools
    assert mcp_server._history is agent_tools._history and agent_tools.TOOLS["ticket_history"][2] is mcp_server._history
