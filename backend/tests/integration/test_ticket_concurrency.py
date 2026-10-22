"""Independent connections and committed rows; no shared Session across requests."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import event, func, select, update
from sqlalchemy.orm import Session

from supportops.config import Settings
from supportops.errors import ApiError
from supportops.main import create_app
from supportops.models import AuditEvent, IdempotencyRecord, Ticket, TicketEvent, TicketMessage, User
from supportops.schemas import TicketPatch
from supportops.security import issue_token
from supportops.ticket_service import patch_ticket


pytestmark = pytest.mark.integration


@pytest.fixture
def committed(pg_engine):
    users = {role: uuid4() for role in ("requester", "manager", "agent-a", "agent-b")}
    ticket_id = uuid4()
    with Session(pg_engine) as session, session.begin():
        for label, user_id in users.items():
            session.add(User(id=user_id, email=f"{user_id}@example.invalid", password_hash="!test-only", active=True,
                role="agent" if label.startswith("agent") else label))
        session.flush()
        session.add(Ticket(id=ticket_id, requester_id=users["requester"], title="Concurrency test", body="Synthetic data"))
        session.flush()
        session.add(TicketEvent(ticket_id=ticket_id, actor_id=users["requester"], event_type="created", changes={}, ticket_version=1))
    app = create_app(Settings(jwt_secret="concurrency-test-secret-" * 3), engine=pg_engine)
    # This module owns a random test schema; rows persist only until its teardown.
    return app, pg_engine, users, ticket_id


def headers(env, who, key):
    app, _, users, _ = env
    return {"Authorization": "Bearer " + issue_token(users[who], app.state.settings), "Idempotency-Key": key}


def counts(engine, ticket_id):
    with Session(engine) as session:
        ticket = session.get(Ticket, ticket_id)
        return ticket.version, ticket.assignee_id, session.scalar(select(func.count()).select_from(TicketEvent).where(TicketEvent.ticket_id == ticket_id)), session.scalar(select(func.count()).select_from(TicketMessage).where(TicketMessage.ticket_id == ticket_id))


def test_two_simultaneous_edits_cannot_both_use_same_version(committed):
    app, engine, users, ticket_id = committed
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            responses = await asyncio.gather(*[
                client.patch(f"/api/tickets/{ticket_id}", headers=headers(committed, "manager", str(uuid4())),
                    json={"expected_version": 1, "assignee_id": str(users[label])}) for label in ("agent-a", "agent-b")
            ])
            assert sorted(response.status_code for response in responses) == [200, 409]
            winner = next(response.json() for response in responses if response.status_code == 200)
            assert str(counts(engine, ticket_id)[1]) == winner["assignee_id"]
    asyncio.run(scenario())
    assert counts(engine, ticket_id)[::2] == (2, 2)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.resource_id == ticket_id)) == 1


@pytest.mark.parametrize("same_body", [True, False])
def test_simultaneous_create_requests_share_one_persisted_result(committed, same_body):
    app, engine, users, _ = committed
    key = str(uuid4())
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            responses = await asyncio.gather(*[
                client.post("/api/tickets", headers=headers(committed, "requester", key),
                    json={"title": "Duplicate creation", "body": "Identical content" if same_body else f"Content{index}"}) for index in range(2)
            ])
            assert sorted(response.status_code for response in responses) == ([201, 201] if same_body else [201, 409])
            if same_body:
                assert responses[0].json() == responses[1].json()
    asyncio.run(scenario())
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Ticket).where(Ticket.requester_id == users["requester"])) == 2
        assert session.scalar(select(func.count()).select_from(IdempotencyRecord).where(IdempotencyRecord.actor_id == users["requester"])) == 1
        assert session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.actor_id == users["requester"])) == 1


def test_simultaneous_message_retry_creates_one_message_and_one_version(committed):
    app, engine, _, ticket_id = committed
    key = str(uuid4())
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            responses = await asyncio.gather(*[
                client.post(f"/api/tickets/{ticket_id}/messages", headers=headers(committed, "requester", key),
                    json={"expected_version": 1, "visibility": "public", "body": "One reply"}) for _ in range(2)
            ])
            assert [response.status_code for response in responses] == [201, 201]
            assert responses[0].json() == responses[1].json()
    asyncio.run(scenario())
    assert counts(engine, ticket_id) == (2, None, 2, 1)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.resource_id == ticket_id)) == 1


def test_assignment_waits_for_concurrent_deactivation_and_rejects_inactive_target(committed):
    app, engine, users, ticket_id = committed
    reached = Event()
    connection = engine.connect()
    transaction = connection.begin()
    connection.execute(update(User).where(User.id == users["agent-a"]).values(active=False))

    def target_query(connection, cursor, statement, parameters, context, executemany):
        if "FOR SHARE" in statement and users["agent-a"] in parameters.values():
            reached.set()

    event.listen(engine, "before_cursor_execute", target_query)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            task = asyncio.create_task(client.patch(f"/api/tickets/{ticket_id}", headers=headers(committed, "manager", str(uuid4())),
                json={"expected_version": 1, "assignee_id": str(users["agent-a"])}))
            try:
                assert await asyncio.to_thread(reached.wait, 3), "Assignment did not reach locked target lookup"
                transaction.commit()
                response = await asyncio.wait_for(task, 5)
                assert response.status_code == 422 and response.json()["error"]["code"] == "assignee_unavailable"
            finally:
                if transaction.is_active:
                    transaction.rollback()
                if not task.done():
                    await asyncio.wait_for(task, 5)
    try:
        asyncio.run(scenario())
    finally:
        event.remove(engine, "before_cursor_execute", target_query)
        if transaction.is_active:
            transaction.rollback()
        connection.close()
    assert counts(engine, ticket_id) == (1, None, 1, 0)


@pytest.mark.parametrize("change,expected", [({"role": "requester"}, 403), ({"active": False}, 401)])
def test_write_rechecks_actor_after_authentication_snapshot(committed, change, expected):
    _, engine, users, ticket_id = committed
    with Session(engine) as session:
        # Represents the identity read performed by the authentication dependency.
        cached = session.get(User, users["manager"])
        assert cached.active and cached.role == "manager"
        with engine.begin() as connection:
            connection.execute(update(User).where(User.id == users["manager"]).values(**change))
        with pytest.raises(ApiError) as error:
            patch_ticket(session, users["manager"], ticket_id,
                TicketPatch(expected_version=1, assignee_id=users["agent-a"]), str(uuid4()))
        assert error.value.status_code == expected
        session.rollback()
    assert counts(engine, ticket_id) == (1, None, 1, 0)
