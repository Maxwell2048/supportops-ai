"""MCP server against real PostgreSQL, driven through the SDK client over Streamable HTTP."""
from contextlib import asynccontextmanager
import json
from uuid import UUID, uuid4

import anyio
import httpx
import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from supportops import mcp_server
from supportops.config import Settings
from supportops.main import create_app
from supportops.models import McpToolCall, Ticket, TicketMessage, User
from supportops.security import issue_token
from supportops.seed import synthetic_id
from test_citations import setup_source
from test_jobs import prepared

pytestmark = pytest.mark.integration

SECRET = "integration-only-mcp-signing-secret-" * 2
SETTINGS = Settings(jwt_secret=SECRET)
BASE = "http://127.0.0.1:8001"
TICKET = synthetic_id("ticket-1")
OTHER = synthetic_id("mcp-ticket-agent-b")
AGENT, MANAGER = synthetic_id("agent-a"), synthetic_id("manager")


@pytest.fixture
def engine(prepared):
    with Session(prepared) as session, session.begin():
        session.execute(insert(Ticket).values(
            id=OTHER, requester_id=synthetic_id("requester-b"), assignee_id=synthetic_id("agent-b"),
            title="Synthetic ticket of agent B", body="Synthetic case assigned only to agent B.",
        ).on_conflict_do_nothing(index_elements=[Ticket.id]))
        session.execute(delete(McpToolCall))
    return prepared


@asynccontextmanager
async def connect(engine, label):
    app = mcp_server.create_mcp_app(SETTINGS, engine=engine)
    headers = {"Authorization": "Bearer " + issue_token(synthetic_id(label), SETTINGS)}
    async with app.router.lifespan_context(app):
        async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app), base_url=BASE, headers=headers) as http:
            async with Client(streamable_http_client(BASE + "/mcp", http_client=http)) as client:
                yield client


def calls(engine, label, *requests):
    async def scenario():
        async with connect(engine, label) as client:
            return [await client.call_tool(name, arguments) for name, arguments in requests]
    return anyio.run(scenario)


def error(result):
    assert result.is_error is True
    return result.structured_content["error"]


def audit(engine):
    with Session(engine) as session:
        return session.scalars(select(McpToolCall).order_by(McpToolCall.created_at, McpToolCall.id)).all()


def rest_detail(engine, label, ticket_id):
    async def scenario():
        app = create_app(SETTINGS, engine=engine)
        headers = {"Authorization": "Bearer " + issue_token(synthetic_id(label), SETTINGS)}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(f"/api/tickets/{ticket_id}", headers=headers)
    return anyio.run(scenario)


def test_agent_cannot_read_another_agents_ticket_and_gets_the_api_not_found(engine):
    listed, mine, other, missing, history = calls(engine, "agent-a",
        ("list_my_tickets", {}), ("get_ticket", {"ticket_id": str(TICKET)}), ("get_ticket", {"ticket_id": str(OTHER)}),
        ("get_ticket", {"ticket_id": str(uuid4())}), ("ticket_history", {"ticket_id": str(OTHER)}))
    ids = {item["id"] for item in listed.structured_content["items"]}
    assert str(TICKET) in ids and str(OTHER) not in ids
    assert mine.is_error is False and mine.structured_content["ticket"]["id"] == str(TICKET)
    with Session(engine) as session:
        assert mine.structured_content["ticket"]["body"] == session.get(Ticket, TICKET).body
    assert not {"requester_id", "requester_email", "contact_phone"} & set(mine.structured_content["ticket"])
    # Out of scope and nonexistent are indistinguishable, and match the REST API's own refusal.
    rest = rest_detail(engine, "agent-a", OTHER).json()["error"]
    for refused in (other, missing, history):
        assert {key: error(refused)[key] for key in ("code", "message", "details")} == {
            "code": rest["code"], "message": rest["message"], "details": []}
    assert rest_detail(engine, "agent-a", OTHER).status_code == 404
    (manager_view,) = calls(engine, "manager", ("get_ticket", {"ticket_id": str(OTHER)}))
    assert manager_view.structured_content["ticket"]["id"] == str(OTHER)


def test_requester_token_is_denied_for_every_tool_even_on_their_own_ticket(engine):
    assert rest_detail(engine, "requester-a", TICKET).status_code == 200
    results = calls(engine, "requester-a", ("list_my_tickets", {}), ("get_ticket", {"ticket_id": str(TICKET)}),
                    ("ticket_history", {"ticket_id": str(TICKET)}), ("search_knowledge", {"query": "sign in"}))
    assert [error(result)["code"] for result in results] == ["forbidden"] * 4
    assert all("Synthetic" not in result.model_dump_json() for result in results)
    rows = audit(engine)
    assert [(row.outcome, row.actor_role, row.ticket_id) for row in rows] == [("forbidden", "requester", None)] * 4


def test_access_changes_mid_session_apply_to_the_next_call(engine):
    async def scenario():
        async with connect(engine, "agent-a") as client:
            first = await client.call_tool("get_ticket", {"ticket_id": str(TICKET)})
            with Session(engine) as session, session.begin():
                session.execute(update(Ticket).where(Ticket.id == TICKET).values(assignee_id=synthetic_id("agent-b")))
            reassigned = await client.call_tool("get_ticket", {"ticket_id": str(TICKET)})
            with Session(engine) as session, session.begin():
                session.execute(update(Ticket).where(Ticket.id == TICKET).values(assignee_id=AGENT))
                session.execute(update(User).where(User.id == AGENT).values(active=False))
            deactivated = await client.call_tool("list_my_tickets", {})
            return first, reassigned, deactivated
    try:
        first, reassigned, deactivated = anyio.run(scenario)
    finally:
        with Session(engine) as session, session.begin():
            session.execute(update(User).where(User.id == AGENT).values(active=True))
    assert first.is_error is False
    assert error(reassigned)["code"] == "not_found"
    assert error(deactivated)["code"] == "invalid_session"
    assert [row.outcome for row in audit(engine)] == ["ok", "not_found", "invalid_session"]


def test_role_downgrade_mid_session_is_denied_on_the_next_call(engine):
    async def scenario():
        async with connect(engine, "manager") as client:
            first = await client.call_tool("list_my_tickets", {})
            with Session(engine) as session, session.begin():
                session.execute(update(User).where(User.id == MANAGER).values(role="requester"))
            return first, await client.call_tool("list_my_tickets", {})
    try:
        first, downgraded = anyio.run(scenario)
    finally:
        with Session(engine) as session, session.begin():
            session.execute(update(User).where(User.id == MANAGER).values(role="manager"))
    assert first.is_error is False and error(downgraded)["code"] == "forbidden"


def test_ticket_history_returns_public_messages_but_never_internal_notes(engine):
    public, internal = "Public synthetic detail " + uuid4().hex, "Internal synthetic note " + uuid4().hex
    with Session(engine) as session, session.begin():
        session.add_all([
            TicketMessage(id=uuid4(), ticket_id=TICKET, author_id=synthetic_id("requester-a"), visibility="public", body=public),
            TicketMessage(id=uuid4(), ticket_id=TICKET, author_id=AGENT, visibility="internal", body=internal),
        ])
    for label in ("agent-a", "manager"):
        (history,) = calls(engine, label, ("ticket_history", {"ticket_id": str(TICKET), "limit": 10}))
        dumped = history.model_dump_json()
        assert history.is_error is False and public in dumped and internal not in dumped
        messages = [row for row in history.structured_content["items"] if row["kind"] == "message"]
        assert messages and all(set(row) == {"kind", "from", "created_at", "body"} for row in messages)
        assert "example.invalid" not in dumped and str(AGENT) not in dumped


def test_search_knowledge_goes_through_scoped_retrieval(engine):
    setup_source(engine, body="Synthetic support source: reset the sign in lock from the account page.")
    setup_source(engine, scope="management", body="Synthetic management escalation matrix for sign in incidents.")
    query = {"query": "escalation matrix", "limit": 10}
    (agent,) = calls(engine, "agent-a", ("search_knowledge", query))
    (manager,) = calls(engine, "manager", ("search_knowledge", query))
    (support,) = calls(engine, "agent-a", ("search_knowledge", {"query": "sign in lock"}))
    assert agent.structured_content["passages"] == [] and agent.structured_content["index_complete"] is True
    assert any("escalation matrix" in row["text"] for row in manager.structured_content["passages"])
    assert any("sign in lock" in row["text"] for row in support.structured_content["passages"])
    assert set(support.structured_content["passages"][0]) == {"article_id", "version_id", "chunk_id", "title", "text", "score"}


def test_every_call_writes_an_audit_row_with_object_ids_but_no_argument_values(engine):
    setup_source(engine)
    results = calls(engine, "agent-a",
        ("list_my_tickets", {"status": "open"}), ("get_ticket", {"ticket_id": str(TICKET)}),
        ("get_ticket", {"ticket_id": str(OTHER)}), ("ticket_history", {"ticket_id": str(TICKET)}),
        ("search_knowledge", {"query": "sign or SECRETMARKER"}), ("search_knowledge", {"query": "SECRET", "extra": "SECRET"}),
        ("close_ticket", {"ticket_id": str(TICKET), "note": "SECRET"}))
    rows = audit(engine)
    assert [(row.tool, row.outcome) for row in rows] == [
        ("list_my_tickets", "ok"), ("get_ticket", "ok"), ("get_ticket", "not_found"), ("ticket_history", "ok"),
        ("search_knowledge", "ok"), ("search_knowledge", "invalid_arguments"), ("unknown", "unknown_tool")]
    assert {(row.actor_id, row.actor_role) for row in rows} == {(AGENT, "agent")}
    assert [row.ticket_id for row in rows] == [None, TICKET, OTHER, TICKET, None, None, None]
    assert str(TICKET) in rows[0].result_ids and rows[1].result_ids == [str(TICKET)] and rows[2].result_ids == []
    passages = results[4].structured_content["passages"]
    assert passages and rows[4].result_ids == [row["chunk_id"] for row in passages] and rows[4].result_count == len(passages)
    assert rows[3].result_count == len(results[3].structured_content["items"])
    # Every response carries the request ID of its audit row.
    for result, row in zip(results, rows, strict=True):
        body = result.structured_content
        assert UUID(body["error"]["request_id"] if result.is_error else body["request_id"]) == row.request_id
    with Session(engine) as session:
        stored = json.dumps([list(row) for row in session.execute(select(McpToolCall.__table__)).all()], default=str)
    assert "SECRET" not in stored and "close_ticket" not in stored


def test_no_result_is_returned_when_the_audit_row_cannot_commit(engine, monkeypatch):
    original = mcp_server.McpToolCall
    monkeypatch.setattr(mcp_server, "McpToolCall", lambda **fields: original(**{**fields, "result_count": -1}))
    (result,) = calls(engine, "agent-a", ("get_ticket", {"ticket_id": str(TICKET)}))
    assert error(result)["code"] == "unavailable" and "Synthetic" not in result.model_dump_json()
    assert audit(engine) == []
