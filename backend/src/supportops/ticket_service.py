"""Write rules. Caller commits once, after business/event/audit/idempotency writes succeed."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from supportops.dependencies import visible_ticket
from supportops.errors import ApiError
from supportops.idempotency import COLLECTION_ID, claim, finish
from supportops.models import AuditEvent, Ticket, TicketEvent, TicketMessage, User
from supportops.schemas import MessageCreate, MessageResponse, MessageWriteResponse, TicketCreate, TicketPatch, TicketSummary
from supportops.security import invalid_session


def _actor(session: Session, user_id: UUID) -> User:
    user = session.scalar(select(User).where(User.id == user_id).with_for_update(read=True).execution_options(populate_existing=True))
    if user is None or not user.active:
        raise invalid_session()
    return user


def _forbidden():
    raise ApiError(403, "forbidden", "Your current role cannot perform this operation")


def _assignee(session: Session, user_id: UUID | None):
    user = session.scalar(select(User).where(User.id == user_id).with_for_update(read=True).execution_options(populate_existing=True)) if user_id else None
    if user is None or not user.active or user.role != "agent":
        raise ApiError(422, "assignee_unavailable", "This assignee is currently unavailable; choose another support agent")


def _version(ticket: Ticket, expected: int):
    if ticket.version != expected:
        raise ApiError(409, "version_conflict", "The ticket has changed; refresh it before continuing")
    if ticket.version >= 2147483647:
        raise ApiError(409, "version_exhausted", "The ticket version limit has been reached")


def _event(session, ticket, actor, kind, changes):
    session.add(TicketEvent(ticket_id=ticket.id, actor_id=actor.id, event_type=kind, changes=changes,
        ticket_version=ticket.version, created_at=datetime.now(timezone.utc)))
    # Explicit allowlist: never copy free text (including reopen reasons) into audit.
    safe_changes = {name: value for name, value in changes.items()
                    if name in {"status", "assignee_id", "priority", "archived", "message_id", "visibility"}}
    session.add(AuditEvent(actor_id=actor.id, actor_role=actor.role, resource_id=ticket.id,
        action="ticket." + kind, request_id=session.info.get("request_id") or uuid4(),
        ticket_version=ticket.version, changes=safe_changes, created_at=datetime.now(timezone.utc)))


def _update(session: Session, ticket: Ticket, expected: int, **values):
    updated = session.execute(update(Ticket).where(Ticket.id == ticket.id, Ticket.version == expected)
        .values(**values, version=expected + 1, updated_at=datetime.now(timezone.utc))
        .returning(Ticket).execution_options(populate_existing=True)).scalar_one_or_none()
    if updated is None:
        raise ApiError(409, "version_conflict", "The ticket has changed; refresh it before continuing")
    return updated


def create_ticket(session: Session, user_id: UUID, payload: TicketCreate, key: str):
    actor = _actor(session, user_id)
    if actor.role != "requester":
        _forbidden()
    record, replay = claim(session, actor.id, COLLECTION_ID, "ticket_create", key, payload)
    if replay:
        return replay
    ticket = Ticket(id=uuid4(), requester_id=actor.id, title=payload.title, body=payload.body)
    session.add(ticket)
    session.flush()
    _event(session, ticket, actor, "created", {"status": {"from": None, "to": "open"}})
    return finish(session, record, 201, TicketSummary.model_validate(ticket))


def patch_ticket(session: Session, user_id: UUID, ticket_id: UUID, payload: TicketPatch, key: str):
    actor = _actor(session, user_id)
    fields = payload.model_fields_set - {"expected_version"}
    if fields & {"assignee_id", "priority", "archived"} and actor.role != "manager":
        _forbidden()
    if actor.role == "requester" and (fields - {"status", "reason"}):
        _forbidden()
    ticket = visible_ticket(session, actor, ticket_id, lock=True)
    # Current role and object authorization always precede cached response lookup.
    record, replay = claim(session, actor.id, ticket.id, "ticket_patch", key, payload)
    if replay:
        return replay
    _version(ticket, payload.expected_version)
    if ticket.archived and not (fields == {"archived"} and payload.archived is False):
        raise ApiError(409, "ticket_archived", "Unarchive the ticket before continuing")

    values, changes = {}, {}
    for name in ("assignee_id", "priority", "archived", "status"):
        if name in fields and getattr(ticket, name) != getattr(payload, name):
            before, after = getattr(ticket, name), getattr(payload, name)
            values[name] = after
            changes[name] = {"from": str(before) if isinstance(before, UUID) else before, "to": str(after) if isinstance(after, UUID) else after}
    if not values:
        raise ApiError(422, "no_changes", "The request contains no actual changes")
    if actor.role == "requester" and (ticket.status, values.get("status")) != ("resolved", "in_progress"):
        _forbidden()
    if "assignee_id" in fields:
        if payload.assignee_id is not None:
            _assignee(session, payload.assignee_id)
        elif ticket.status in {"in_progress", "waiting_customer"}:
            raise ApiError(409, "assignee_required", "Tickets in progress or waiting for a customer must retain an assignee")
    if "archived" in values and ticket.status != "closed":
        raise ApiError(409, "invalid_archive", "Only closed tickets can be archived or unarchived")

    public_body = None
    if "status" in values:
        transition = ticket.status, values["status"]
        allowed = {("open", "in_progress"), ("in_progress", "waiting_customer"),
                   ("waiting_customer", "in_progress"), ("in_progress", "resolved"),
                   ("waiting_customer", "resolved"), ("resolved", "in_progress"),
                   ("resolved", "closed"), ("closed", "open")}
        if transition not in allowed:
            raise ApiError(409, "invalid_transition", "This status transition is not allowed")
        if transition in {("resolved", "closed"), ("closed", "open")} and actor.role != "manager":
            _forbidden()
        if transition in {("resolved", "in_progress"), ("closed", "open")}:
            if not payload.reason or "assignee_id" in fields:
                raise ApiError(422, "reopen_reason_required", "Reopening requires a reason and must follow the assignee rules")
            public_body = payload.reason
            if transition == ("closed", "open"):
                values["assignee_id"] = None
                changes["assignee_id"] = {"from": str(ticket.assignee_id) if ticket.assignee_id else None, "to": None}
        elif payload.reason is not None:
            raise ApiError(422, "unexpected_reason", "The reason field is only valid when reopening a ticket")
        if values["status"] in {"waiting_customer", "resolved"}:
            if not payload.public_reply:
                raise ApiError(422, "public_reply_required", "A public reply is required when waiting for a customer or resolving a ticket")
            public_body = payload.public_reply
        elif payload.public_reply is not None:
            raise ApiError(422, "unexpected_public_reply", "This transition does not accept public_reply; use the messages endpoint")
        if values["status"] == "in_progress":
            _assignee(session, values.get("assignee_id", ticket.assignee_id))
    elif payload.reason is not None or payload.public_reply is not None:
        raise ApiError(422, "unexpected_reply", "Reason and public reply fields require their corresponding status transitions")

    if values.get("archived", ticket.archived) and values.get("status", ticket.status) != "closed":
        raise ApiError(409, "invalid_archive", "Archived tickets must remain closed")
    ticket = _update(session, ticket, payload.expected_version, **values)
    if public_body:
        message = TicketMessage(id=uuid4(), ticket_id=ticket.id, author_id=actor.id, visibility="public", body=public_body, created_at=datetime.now(timezone.utc))
        session.add(message)
        changes["message_id"] = str(message.id)
    if payload.reason:
        changes["reason"] = payload.reason
    kind = "assigned" if set(values) == {"assignee_id"} else "updated"
    _event(session, ticket, actor, kind, changes)
    return finish(session, record, 200, TicketSummary.model_validate(ticket))


def add_message(session: Session, user_id: UUID, ticket_id: UUID, payload: MessageCreate, key: str):
    actor = _actor(session, user_id)
    if actor.role == "requester" and payload.visibility != "public":
        _forbidden()
    ticket = visible_ticket(session, actor, ticket_id, lock=True)
    record, replay = claim(session, actor.id, ticket.id, "ticket_message", key, payload)
    if replay:
        return replay
    _version(ticket, payload.expected_version)
    if ticket.archived or ticket.status == "closed":
        raise ApiError(409, "ticket_not_writable", "Messages cannot be added to closed or archived tickets")
    ticket = _update(session, ticket, payload.expected_version)
    message = TicketMessage(id=uuid4(), ticket_id=ticket.id, author_id=actor.id, visibility=payload.visibility, body=payload.body, created_at=datetime.now(timezone.utc))
    session.add(message)
    session.flush()
    _event(session, ticket, actor, "message_added", {"message_id": str(message.id), "visibility": message.visibility})
    return finish(session, record, 201, MessageWriteResponse(message=MessageResponse.model_validate(message), ticket_version=ticket.version))
