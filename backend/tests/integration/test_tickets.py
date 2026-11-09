import asyncio
from datetime import datetime, timezone
from itertools import product
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import event, func, select, update
from sqlalchemy.orm import Session

from supportops.config import Settings
from supportops.dependencies import get_session
from supportops.main import create_app
from supportops.models import IdempotencyRecord, Ticket, TicketEvent, TicketMessage, User
from supportops.security import issue_token
from supportops.seed import seed, synthetic_id


pytestmark = pytest.mark.integration
SECRET = "ticket-tests-only-signing-secret-" * 2
TICKET_ID = synthetic_id("ticket-1")
PATH = f"/api/tickets/{TICKET_ID}"


@pytest.fixture
def env(pg_engine):
    # API commits release request savepoints; the outer transaction is rolled back.
    connection = pg_engine.connect()
    outer = connection.begin()
    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        seed(session)
        session.execute(update(User).values(active=True))
        session.commit()
    app = create_app(Settings(jwt_secret=SECRET), engine=pg_engine)

    def session_for_request():
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session

    app.dependency_overrides[get_session] = session_for_request
    try:
        yield app, connection
    finally:
        outer.rollback()
        connection.close()


def call(env, method, path=PATH, *, who="manager", payload=None, key=None, params=None, omit_key=False, token=None):
    app, _ = env
    token = token or issue_token(synthetic_id(who), app.state.settings)
    headers = {"Authorization": "Bearer " + token}
    if method != "GET" and not omit_key:
        headers["Idempotency-Key"] = key or str(uuid4())
    async def execute():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, path, headers=headers, json=payload, params=params)
    return asyncio.run(execute())


def state(env):
    connection = env[1]
    row = connection.execute(select(Ticket.version, Ticket.assignee_id, Ticket.status, Ticket.archived).where(Ticket.id == TICKET_ID)).one()
    counts = [connection.scalar(select(func.count()).select_from(model)) for model in (TicketEvent, TicketMessage, IdempotencyRecord)]
    return row, counts


def setup_ticket(env, **values):
    env[1].execute(update(Ticket).where(Ticket.id == TICKET_ID).values(**values))


def test_creation_uses_current_identity_and_replays_one_result(env):
    body = {"title": " New synthetic issue ", "body": " Test description "}
    first = call(env, "POST", "/api/tickets", who="requester-a", payload=body, key="create-once")
    second = call(env, "POST", "/api/tickets", who="requester-a", payload=body, key="create-once")
    assert first.status_code == second.status_code == 201 and first.json() == second.json()
    ticket = first.json()
    assert ticket["requester_id"] == str(synthetic_id("requester-a"))
    assert ticket["title"] == "New synthetic issue" and ticket["body"] == "Test description"
    assert ticket["version"] == 1 and ticket["status"] == "open" and ticket["assignee_id"] is None
    assert call(env, "GET", f"/api/tickets/{ticket['id']}", who="requester-b").status_code == 404
    assert env[1].scalar(select(func.count()).select_from(Ticket)) == 2
    assert state(env)[1] == [2, 0, 1]


@pytest.mark.parametrize("extra", [{"requester_id": str(uuid4())}, {"requester_email": "other@example.invalid"}, {"assignee_id": str(uuid4())}, {"status": "closed"}, {"role": "manager"}])
def test_creation_cannot_inject_ownership_or_privileged_fields(env, extra):
    response = call(env, "POST", "/api/tickets", who="requester-a", payload={"title": "Test", "body": "Description", **extra})
    assert response.status_code == 422 and state(env)[1] == [1, 0, 0]


@pytest.mark.parametrize("who", ["agent-a", "manager"])
def test_only_requesters_can_create_tickets(env, who):
    assert call(env, "POST", "/api/tickets", who=who, payload={"title": "Test", "body": "Description"}).status_code == 403


def test_creation_key_is_bound_to_body_and_identity(env):
    body = {"title": "Test", "body": "Description"}
    first = call(env, "POST", "/api/tickets", who="requester-a", payload=body, key="shared-key")
    assert first.status_code == 201
    assert call(env, "POST", "/api/tickets", who="requester-a", payload={**body, "body": "Different description"}, key="shared-key").status_code == 409
    other = call(env, "POST", "/api/tickets", who="requester-b", payload=body, key="shared-key")
    assert other.status_code == 201 and first.json()["id"] != other.json()["id"]


def test_assignment_replay_conflict_noop_and_version_conflict(env):
    body = {"expected_version": 1, "assignee_id": str(synthetic_id("agent-a"))}
    first = call(env, "PATCH", payload=body, key="assign-once")
    assert first.status_code == 200 and first.json()["version"] == 2 and first.json()["status"] == "open"
    assert call(env, "PATCH", payload=body, key="assign-once").json() == first.json()
    assert call(env, "PATCH", payload={**body, "assignee_id": str(synthetic_id("agent-b"))}, key="assign-once").status_code == 409
    assert call(env, "PATCH", payload={**body, "assignee_id": str(synthetic_id("agent-b"))}).json()["error"]["code"] == "version_conflict"
    assert call(env, "PATCH", payload={**body, "expected_version": 2}).json()["error"]["code"] == "no_changes"
    assert state(env)[1] == [2, 0, 1]
    latest = call(env, "GET", PATH + "/events").json()[-1]
    assert latest["event_type"] == "assigned" and latest["actor_id"] == str(synthetic_id("manager"))
    assert latest["changes"]["assignee_id"] == {"from": None, "to": str(synthetic_id("agent-a"))}


@pytest.mark.parametrize("kind", ["inactive", "requester", "missing"])
def test_assignment_checks_current_target_state(env, kind):
    target = synthetic_id("agent-a")
    if kind == "inactive":
        # A previously displayed valid target becomes inactive before submission.
        assert env[1].scalar(select(User.active).where(User.id == target))
        env[1].execute(update(User).where(User.id == target).values(active=False))
    elif kind == "requester":
        target = synthetic_id("requester-b")
    else:
        target = uuid4()
    response = call(env, "PATCH", payload={"expected_version": 1, "assignee_id": str(target)})
    assert response.status_code == 422 and response.json()["error"]["code"] == "assignee_unavailable"
    assert state(env)[0].version == 1 and state(env)[1] == [1, 0, 0]


@pytest.mark.parametrize("who", ["requester-a", "agent-a"])
def test_nonmanager_cannot_assign_or_change_priority(env, who):
    setup_ticket(env, assignee_id=synthetic_id("agent-a"))
    for fields in [{"assignee_id": str(synthetic_id("agent-b"))}, {"priority": "urgent"}]:
        assert call(env, "PATCH", who=who, payload={"expected_version": 1, **fields}).status_code == 403
    assert state(env)[1] == [1, 0, 0]


@pytest.mark.parametrize("status", ["in_progress", "waiting_customer"])
def test_active_work_cannot_clear_assignee(env, status):
    setup_ticket(env, status=status, assignee_id=synthetic_id("agent-a"))
    response = call(env, "PATCH", payload={"expected_version": 1, "assignee_id": None})
    assert response.status_code == 409 and state(env)[0].assignee_id == synthetic_id("agent-a")
    assert state(env)[1] == [1, 0, 0]


STATES = ["open", "in_progress", "waiting_customer", "resolved", "closed"]
ALLOWED = {("open", "in_progress"), ("in_progress", "waiting_customer"), ("waiting_customer", "in_progress"),
           ("in_progress", "resolved"), ("waiting_customer", "resolved"), ("resolved", "in_progress"),
           ("resolved", "closed"), ("closed", "open")}


@pytest.mark.parametrize("old,new", [(a, b) for a, b in product(STATES, STATES) if a != b])
def test_manager_state_transition_matrix(env, old, new):
    setup_ticket(env, status=old, assignee_id=synthetic_id("agent-a"))
    body = {"expected_version": 1, "status": new}
    if new in {"waiting_customer", "resolved"}:
        body["public_reply"] = "Human resolution summary"
    if (old, new) in {("resolved", "in_progress"), ("closed", "open")}:
        body["reason"] = "Synthetic reopening reason"
    response = call(env, "PATCH", payload=body)
    assert response.status_code == (200 if (old, new) in ALLOWED else 409)
    if response.status_code == 200:
        assert response.json()["version"] == 2 and response.json()["status"] == new
        assert state(env)[1][0] == 2
        assert state(env)[1][1] == int("public_reply" in body or "reason" in body)
        if (old, new) == ("closed", "open"):
            assert response.json()["assignee_id"] is None
    else:
        assert state(env)[0].version == 1 and state(env)[1] == [1, 0, 0]


def test_start_requires_active_assignee_and_can_combine_assignment(env):
    assert call(env, "PATCH", payload={"expected_version": 1, "status": "in_progress"}).status_code == 422
    response = call(env, "PATCH", payload={"expected_version": 1, "status": "in_progress", "assignee_id": str(synthetic_id("agent-a"))})
    assert response.status_code == 200 and state(env)[1] == [2, 0, 1]


@pytest.mark.parametrize("old,new", [("in_progress", "waiting_customer"), ("waiting_customer", "resolved"), ("resolved", "in_progress"), ("closed", "open")])
def test_transition_requires_reply_or_reopen_reason(env, old, new):
    setup_ticket(env, status=old, assignee_id=synthetic_id("agent-a"))
    assert call(env, "PATCH", payload={"expected_version": 1, "status": new}).status_code == 422
    assert state(env)[1] == [1, 0, 0]


def test_requester_reopen_preserves_assignee_and_publishes_reason(env):
    setup_ticket(env, status="resolved", assignee_id=synthetic_id("agent-a"))
    result = call(env, "PATCH", who="requester-a", payload={"expected_version": 1, "status": "in_progress", "reason": "The issue has returned"})
    assert result.status_code == 200 and result.json()["assignee_id"] == str(synthetic_id("agent-a"))
    detail = call(env, "GET", who="requester-a").json()
    assert detail["messages"][0]["body"] == "The issue has returned" and "events" not in detail


@pytest.mark.parametrize("who,old,new", [("requester-a", "open", "in_progress"), ("requester-a", "closed", "open"), ("agent-a", "resolved", "closed")])
def test_role_cannot_bypass_state_permissions(env, who, old, new):
    setup_ticket(env, status=old, assignee_id=synthetic_id("agent-a"))
    assert call(env, "PATCH", who=who, payload={"expected_version": 1, "status": new, "reason": "Test reason"}).status_code == 403


def test_archive_is_separate_and_only_unarchive_can_write_archived_ticket(env):
    assert call(env, "PATCH", payload={"expected_version": 1, "archived": True}).status_code == 409
    setup_ticket(env, status="closed", assignee_id=synthetic_id("agent-a"))
    body = {"expected_version": 1, "archived": True}
    archived = call(env, "PATCH", payload=body, key="archive")
    assert archived.status_code == 200 and archived.json()["status"] == "closed"
    assert call(env, "PATCH", payload=body, key="archive").json() == archived.json()
    assert call(env, "PATCH", payload={"expected_version": 2, "assignee_id": str(synthetic_id("agent-b"))}).status_code == 409
    assert call(env, "PATCH", payload={"expected_version": 2, "archived": False, "status": "open", "reason": "Test"}).status_code == 409
    assert call(env, "PATCH", payload={"expected_version": 2, "archived": False}).status_code == 200
    assert call(env, "PATCH", payload={"expected_version": 3, "status": "open", "reason": "Test"}).status_code == 200
    assert state(env)[0].assignee_id is None


def test_cannot_reopen_and_archive_in_same_patch(env):
    setup_ticket(env, status="closed")
    response = call(env, "PATCH", payload={"expected_version": 1, "status": "open", "reason": "Test", "archived": True})
    assert response.status_code == 409 and state(env)[1] == [1, 0, 0]


@pytest.mark.parametrize("who,visibility", [("requester-a", "public"), ("agent-a", "internal"), ("manager", "public"), ("manager", "internal")])
def test_message_authorship_visibility_and_idempotency(env, who, visibility):
    setup_ticket(env, status="waiting_customer", assignee_id=synthetic_id("agent-a"))
    payload = {"expected_version": 1, "visibility": visibility, "body": "Synthetic reply content"}
    first = call(env, "POST", PATH + "/messages", who=who, payload=payload, key="message-once")
    repeated = call(env, "POST", PATH + "/messages", who=who, payload=payload, key="message-once")
    assert first.status_code == repeated.status_code == 201 and first.json() == repeated.json()
    assert first.json()["message"]["author_id"] == str(synthetic_id(who)) and first.json()["ticket_version"] == 2
    assert state(env)[0].status == "waiting_customer" and state(env)[1] == [2, 1, 1]
    own_detail = call(env, "GET", who="requester-a").json()
    assert len(own_detail["messages"]) == (1 if visibility == "public" else 0)
    assert call(env, "POST", PATH + "/messages", who=who, payload={**payload, "body": "Different content"}, key="message-once").status_code == 409


@pytest.mark.parametrize("who,visibility,status", [("requester-a", "internal", 403), ("requester-b", "public", 404), ("agent-b", "public", 404)])
def test_message_permissions_do_not_mutate_state(env, who, visibility, status):
    setup_ticket(env, assignee_id=synthetic_id("agent-a"))
    response = call(env, "POST", PATH + "/messages", who=who, payload={"expected_version": 1, "visibility": visibility, "body": "Test"})
    assert response.status_code == status and state(env)[1] == [1, 0, 0]


@pytest.mark.parametrize("archived", [False, True])
def test_closed_or_archived_ticket_cannot_receive_messages(env, archived):
    setup_ticket(env, status="closed", archived=archived)
    assert call(env, "POST", PATH + "/messages", payload={"expected_version": 1, "visibility": "public", "body": "Test"}).status_code == 409


def test_transfer_revokes_cached_message_replay_and_detail_access(env):
    setup_ticket(env, assignee_id=synthetic_id("agent-a"))
    body = {"expected_version": 1, "visibility": "internal", "body": "Internal details"}
    assert call(env, "POST", PATH + "/messages", who="agent-a", payload=body, key="old-agent").status_code == 201
    assert call(env, "PATCH", payload={"expected_version": 2, "assignee_id": str(synthetic_id("agent-b"))}).status_code == 200
    assert call(env, "POST", PATH + "/messages", who="agent-a", payload=body, key="old-agent").status_code == 404
    assert call(env, "GET", who="agent-a").status_code == 404
    assert call(env, "GET", who="agent-b").status_code == 200


def test_role_downgrade_cannot_replay_internal_message(env):
    setup_ticket(env, requester_id=synthetic_id("agent-a"), assignee_id=synthetic_id("agent-a"))
    payload = {"expected_version": 1, "visibility": "internal", "body": "Original internal note"}
    assert call(env, "POST", PATH + "/messages", who="agent-a", payload=payload, key="private-result").status_code == 201
    env[1].execute(update(User).where(User.id == synthetic_id("agent-a")).values(role="requester"))
    response = call(env, "POST", PATH + "/messages", who="agent-a", payload=payload, key="private-result")
    assert response.status_code == 403 and "Original internal note" not in response.text


@pytest.mark.parametrize("operation", ["create", "patch", "message"])
def test_event_failure_rolls_back_business_and_idempotency_then_retry_succeeds(env, operation):
    def corrupt_event(session, context, instances):
        for record in session.new:
            if isinstance(record, TicketEvent):
                record.actor_id = uuid4()  # Real FK failure during flush.
    if operation == "create":
        args = ("POST", "/api/tickets")
        kwargs = {"who": "requester-a", "payload": {"title": "Test", "body": "Description"}}
    elif operation == "patch":
        args = ("PATCH", PATH)
        kwargs = {"payload": {"expected_version": 1, "assignee_id": str(synthetic_id("agent-a"))}}
    else:
        args = ("POST", PATH + "/messages")
        kwargs = {"payload": {"expected_version": 1, "visibility": "public", "body": "Test"}}
    event.listen(Session, "before_flush", corrupt_event)
    try:
        assert call(env, *args, **kwargs, key="retry-after-failure").status_code == 503
    finally:
        event.remove(Session, "before_flush", corrupt_event)
    assert state(env)[0].version == 1 and state(env)[1] == [1, 0, 0]
    assert env[1].scalar(select(func.count()).select_from(Ticket)) == 1
    assert call(env, *args, **kwargs, key="retry-after-failure").status_code in {200, 201}


@pytest.mark.parametrize("payload", [{"expected_version": 0}, {"expected_version": True}, {"expected_version": "1"},
    {"expected_version": 1, "status": None}, {"expected_version": 1, "priority": "invalid"},
    {"expected_version": 1, "archived": "false"}, {"expected_version": 1, "requester_id": str(uuid4())}])
def test_patch_rejects_invalid_or_untrusted_fields(env, payload):
    assert call(env, "PATCH", payload=payload).status_code == 422
    assert state(env)[1] == [1, 0, 0]


def test_missing_idempotency_key_and_spoofed_message_author_are_rejected(env):
    assert call(env, "PATCH", payload={"expected_version": 1, "priority": "high"}, omit_key=True).status_code == 422
    assert call(env, "POST", PATH + "/messages", payload={"expected_version": 1, "visibility": "public", "body": "Test", "author_id": str(uuid4())}).status_code == 422


def test_postgres_unsupported_null_text_is_a_client_error_without_writes(env):
    assert call(env, "POST", "/api/tickets", who="requester-a", payload={"title": "Test", "body": "bad\x00text"}).status_code == 422
    assert call(env, "GET", "/api/tickets", params={"q": "bad\x00query"}).status_code == 422
    assert call(env, "POST", PATH + "/messages", payload={"expected_version": 1, "visibility": "public", "body": "bad\x00reply"}).status_code == 422
    assert state(env)[1] == [1, 0, 0]


def test_idempotency_key_is_independently_scoped_by_resource_and_operation(env):
    created = call(env, "POST", "/api/tickets", who="requester-a", payload={"title": "Second issue", "body": "Test"}).json()
    for path in [PATH, f"/api/tickets/{created['id']}"]:
        assert call(env, "PATCH", path, payload={"expected_version": 1, "priority": "high"}, key="same-key").status_code == 200
    assert call(env, "POST", PATH + "/messages", payload={"expected_version": 2, "visibility": "public", "body": "Test"}, key="same-key").status_code == 201
    assert env[1].scalar(select(func.count()).select_from(IdempotencyRecord)) == 4


def fill_list(env):
    timestamp = datetime(2020, 1, 1, tzinfo=timezone.utc)
    for number in range(1, 8):
        env[1].execute(Ticket.__table__.insert().values(id=UUID(int=number), requester_id=synthetic_id("requester-a"),
            title=f"needle {number}", body="synthetic description", created_at=timestamp))


def test_keyset_pagination_handles_equal_times_and_new_insert_without_duplicates(env):
    fill_list(env)
    first = call(env, "GET", "/api/tickets", who="requester-a", params={"q": "needle", "limit": 2})
    assert first.status_code == 200
    seen = [row["id"] for row in first.json()["items"]]
    assert seen == [str(UUID(int=7)), str(UUID(int=6))]
    env[1].execute(Ticket.__table__.insert().values(id=uuid4(), requester_id=synthetic_id("requester-a"), title="needle new", body="new insert"))
    cursor = first.json()["next_cursor"]
    while cursor:
        page = call(env, "GET", "/api/tickets", who="requester-a", params={"q": "needle", "limit": 2, "cursor": cursor})
        assert page.status_code == 200
        seen.extend(row["id"] for row in page.json()["items"])
        cursor = page.json()["next_cursor"]
    assert seen == [str(UUID(int=number)) for number in range(7, 0, -1)]


def test_cursor_is_bound_to_filters_identity_role_and_cannot_be_used_as_auth(env):
    fill_list(env)
    cursor = call(env, "GET", "/api/tickets", who="requester-a", params={"limit": 2}).json()["next_cursor"]
    assert cursor
    assert call(env, "GET", "/api/tickets", who="requester-b", params={"limit": 2, "cursor": cursor}).status_code == 422
    assert call(env, "GET", "/api/tickets", who="requester-a", params={"limit": 3, "cursor": cursor}).status_code == 422
    parts = cursor.split(".")
    parts[2] = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
    assert call(env, "GET", "/api/tickets", who="requester-a", params={"limit": 2, "cursor": ".".join(parts)}).status_code == 422
    assert call(env, "GET", "/api/me", token=cursor).status_code == 401
    env[1].execute(update(User).where(User.id == synthetic_id("requester-a")).values(role="manager"))
    assert call(env, "GET", "/api/tickets", who="requester-a", params={"limit": 2, "cursor": cursor}).status_code == 422


def test_list_scope_filters_and_literal_search_do_not_leak_internal_notes(env):
    setup_ticket(env, title="literal %_ marker", priority="high", assignee_id=synthetic_id("agent-a"))
    for who, count in [("requester-a", 1), ("requester-b", 0), ("agent-a", 1), ("agent-b", 0), ("manager", 1)]:
        response = call(env, "GET", "/api/tickets", who=who, params={"q": "%_", "priority": "high", "status": "open", "assignee_id": str(synthetic_id("agent-a"))})
        assert response.status_code == 200 and len(response.json()["items"]) == count
        assert "messages" not in response.text and "events" not in response.text
    assert call(env, "POST", PATH + "/messages", payload={"expected_version": 1, "visibility": "internal", "body": "secret-note-keyword"}).status_code == 201
    assert call(env, "GET", "/api/tickets", who="requester-a", params={"q": "secret-note-keyword"}).json()["items"] == []
    assert call(env, "GET", "/api/tickets", params={"q": "%' OR 1=1--"}).json()["items"] == []


def test_optional_contact_phone_and_staff_email_are_scoped(env):
    from supportops.models import AuditEvent
    payload = {"title": "Contact request", "body": "Synthetic issue", "contact_phone": " +61 400 123 456 "}
    response = call(env, "POST", "/api/tickets", who="requester-a", payload=payload, key="contact-once")
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["contact_phone"] == "+61 400 123 456"
    assert call(env, "POST", "/api/tickets", who="requester-a", payload=payload, key="contact-once").json() == ticket
    path = f"/api/tickets/{ticket['id']}"
    assert call(env, "GET", path, who="requester-b").status_code == 404
    assert call(env, "GET", path, who="agent-b").status_code == 404
    owner = call(env, "GET", path, who="requester-a").json()
    assert owner["contact_phone"] == "+61 400 123 456" and "requester_email" not in owner
    manager = call(env, "GET", path, who="manager").json()
    assert manager["contact_phone"] == "+61 400 123 456"
    assert manager["requester_email"] == "requester-a@example.invalid"
    audit = env[1].execute(select(AuditEvent.changes).where(AuditEvent.resource_id == UUID(ticket["id"]))).scalars().all()
    assert "+61 400 123 456" not in str(audit)


@pytest.mark.parametrize("value", ["abc", "---", "1" * 41, "123\n456", "\x00"])
def test_invalid_contact_phone_is_rejected(env, value):
    response = call(env, "POST", "/api/tickets", who="requester-a", payload={"title": "Contact", "body": "Synthetic", "contact_phone": value})
    assert response.status_code == 422
