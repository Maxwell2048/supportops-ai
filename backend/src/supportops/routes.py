from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from supportops.dependencies import CurrentUser, DbSession, StaffUser, visible_ticket
from supportops.errors import ApiError
from supportops.models import TicketEvent, TicketMessage, User
from supportops.schemas import EventResponse, LoginInput, MessageResponse, StaffTicketResponse, TicketResponse, TokenResponse, UserResponse
from supportops.security import issue_token, require_auth_config, verify_password
from supportops.schemas import MessageCreate, MessageWriteResponse, TicketCreate, TicketPage, TicketPatch, TicketQuery, TicketSummary
from supportops import ticket_service, jobs, reviews
from supportops.ticket_queries import list_tickets as query_tickets
from supportops.audit_queries import list_audit_events
from supportops.schemas import AuditPage, AuditQuery


router = APIRouter(prefix="/api")
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]


@router.get('/audit-events', response_model=AuditPage, tags=['audit'])
def audit_list(request: Request, user: CurrentUser, session: DbSession, query: Annotated[AuditQuery, Query()]):
    return list_audit_events(session, user, query, request.app.state.settings)


@router.post("/auth/login", response_model=TokenResponse, tags=["auth"])
def login(payload: LoginInput, request: Request, session: DbSession):
    settings = request.app.state.settings
    require_auth_config(settings)
    # Do not read X-Forwarded-For here; configure trusted proxies at deployment.
    ip = request.client.host if request.client else "unknown"
    request.app.state.login_limiter.check(payload.email, ip)
    user = session.scalar(select(User).where(User.email == payload.email))
    valid = verify_password(payload.password.get_secret_value(), user.password_hash if user else None)
    if not valid or user is None or not user.active:
        raise ApiError(401, "invalid_credentials", "Incorrect email or password", {"WWW-Authenticate": "Bearer"})
    request.state.actor_id = str(user.id)
    request.state.actor_role = user.role
    return TokenResponse(access_token=issue_token(user.id, settings), expires_in=settings.access_token_minutes * 60)


@router.get("/me", response_model=UserResponse, tags=["auth"])
def me(user: CurrentUser):
    return UserResponse.model_validate(user)


@router.get("/agents", response_model=list[UserResponse], tags=["tickets"])
def available_agents(user: CurrentUser, session: DbSession):
    if user.role != "manager":
        raise ApiError(403, "forbidden", "Only managers can read the assignment directory")
    statement = select(User).where(User.role == "agent", User.active.is_(True)).order_by(User.email, User.id)
    return [UserResponse.model_validate(row) for row in session.scalars(statement)]


@router.get("/tickets", response_model=TicketPage, tags=["tickets"])
def ticket_list(request: Request, user: CurrentUser, session: DbSession, query: Annotated[TicketQuery, Query()]):
    return query_tickets(session, user, query, request.app.state.settings)


def _commit_write(session, result):
    response = JSONResponse(status_code=result.status, content=result.body)
    session.commit()
    return response


@router.post("/tickets", response_model=TicketSummary, status_code=201, tags=["tickets"])
def ticket_create(payload: TicketCreate, request: Request, user: CurrentUser, session: DbSession, key: IdempotencyKey):
    session.info["request_id"] = UUID(request.state.request_id)
    return _commit_write(session, ticket_service.create_ticket(session, user.id, payload, key))


@router.patch("/tickets/{ticket_id}", response_model=TicketSummary, tags=["tickets"])
def ticket_patch(ticket_id: UUID, payload: TicketPatch, request: Request, user: CurrentUser, session: DbSession, key: IdempotencyKey):
    session.info["request_id"] = UUID(request.state.request_id)
    return _commit_write(session, ticket_service.patch_ticket(session, user.id, ticket_id, payload, key))


@router.post("/tickets/{ticket_id}/messages", response_model=MessageWriteResponse, status_code=201, tags=["tickets"])
def ticket_message(ticket_id: UUID, payload: MessageCreate, request: Request, user: CurrentUser, session: DbSession, key: IdempotencyKey):
    session.info["request_id"] = UUID(request.state.request_id)
    return _commit_write(session, ticket_service.add_message(session, user.id, ticket_id, payload, key))


@router.get("/tickets/{ticket_id}", response_model=StaffTicketResponse | TicketResponse, tags=["tickets"])
def ticket_detail(ticket_id: UUID, user: CurrentUser, session: DbSession):
    ticket = visible_ticket(session, user, ticket_id)
    statement = select(TicketMessage).where(TicketMessage.ticket_id == ticket_id)
    if user.role == "requester":
        statement = statement.where(TicketMessage.visibility == "public")
    messages = [MessageResponse.model_validate(row) for row in session.scalars(statement.order_by(TicketMessage.created_at, TicketMessage.id))]
    fields = {name: getattr(ticket, name) for name in TicketResponse.model_fields if name != "messages"}
    if user.role == "requester":
        return TicketResponse(**fields, messages=messages)
    events = _events(session, ticket_id)
    return StaffTicketResponse(**fields, messages=messages, events=events)


def _events(session, ticket_id):
    statement = select(TicketEvent).where(TicketEvent.ticket_id == ticket_id).order_by(TicketEvent.ticket_version)
    return [EventResponse.model_validate(row) for row in session.scalars(statement)]


@router.get("/tickets/{ticket_id}/events", response_model=list[EventResponse], tags=["tickets"])
def ticket_events(ticket_id: UUID, user: StaffUser, session: DbSession):
    visible_ticket(session, user, ticket_id)
    return _events(session, ticket_id)

@router.post("/tickets/{ticket_id}/analysis-jobs", status_code=202, tags=["analysis"])
def analysis_create(ticket_id: UUID, payload: jobs.JobCreate, user: CurrentUser, session: DbSession, key: IdempotencyKey):
    return _commit_write(session, jobs.create_job(session, user.id, ticket_id, payload, key))


@router.get("/analysis-jobs/{job_id}", tags=["analysis"])
def analysis_read(job_id: UUID, user: CurrentUser, session: DbSession):
    return jobs.read_job(session, user, job_id)

@router.get("/analysis-jobs/{job_id}/suggestion", tags=["analysis"])
def suggestion_read(job_id: UUID, user: CurrentUser, session: DbSession):
    return reviews.get_suggestion(session, user, job_id)


@router.post("/suggestions/{job_id}/review", tags=["analysis"])
def suggestion_review(job_id: UUID, payload: reviews.ReviewInput, request: Request, user: CurrentUser, session: DbSession, key: IdempotencyKey):
    session.info["request_id"] = UUID(request.state.request_id)
    return _commit_write(session, reviews.review(session, user.id, job_id, payload, key))
