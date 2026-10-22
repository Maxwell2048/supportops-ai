from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from supportops.errors import ApiError
from supportops.models import Ticket, User
from supportops.security import decode_subject, invalid_session


BEARER = HTTPBearer(auto_error=False)


def get_session(request: Request):
    engine = request.app.state.engine
    if engine is None:
        raise ApiError(503, "database_unavailable", "The service is temporarily unavailable; please try again later")
    with Session(engine) as session:
        yield session


DbSession = Annotated[Session, Depends(get_session)]


def get_current_user(
    request: Request, session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(BEARER)],
) -> User:
    if credentials is None:
        raise invalid_session()
    user_id = decode_subject(credentials.credentials, request.app.state.settings)
    user = session.get(User, user_id)
    if user is None or not user.active:
        raise invalid_session()
    request.state.actor_id = str(user.id)
    request.state.actor_role = user.role
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_staff(user: CurrentUser) -> User:
    if user.role not in {"agent", "manager"}:
        raise ApiError(403, "forbidden", "Your current role cannot use this feature")
    return user


StaffUser = Annotated[User, Depends(require_staff)]


def scoped_tickets(user: User):
    statement = select(Ticket)
    if user.role == "requester":
        statement = statement.where(Ticket.requester_id == user.id)
    elif user.role == "agent":
        statement = statement.where(Ticket.assignee_id == user.id)
    elif user.role != "manager":
        raise ApiError(403, "forbidden", "Your current role cannot use this feature")
    return statement


def visible_ticket(session: Session, user: User, ticket_id, *, lock=False) -> Ticket:
    statement = scoped_tickets(user).where(Ticket.id == ticket_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    ticket = session.scalar(statement)
    if ticket is None:
        raise ApiError(404, "not_found", "The ticket does not exist or is not accessible")
    return ticket
