from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from sqlalchemy import or_, tuple_

from supportops.dependencies import scoped_tickets
from supportops.errors import ApiError
from supportops.idempotency import canonical_hash
from supportops.models import Ticket
from supportops.schemas import TicketPage, TicketQuery, TicketSummary
from supportops.security import require_auth_config


def list_tickets(session, user, query: TicketQuery, settings):
    scope = canonical_hash(query.model_dump(mode="json", exclude={"cursor"}))
    statement = scoped_tickets(user)
    for name in ("status", "priority", "assignee_id"):
        value = getattr(query, name)
        if value is not None:
            statement = statement.where(getattr(Ticket, name) == value)
    if query.q:
        statement = statement.where(or_(Ticket.title.icontains(query.q, autoescape=True), Ticket.body.icontains(query.q, autoescape=True)))
    secret = require_auth_config(settings)
    audience = settings.jwt_audience + ":ticket-list"
    if query.cursor:
        try:
            claims = jwt.decode(query.cursor, secret, algorithms=["HS256"], issuer=settings.jwt_issuer, audience=audience,
                options={"require": ["sub", "role", "scope", "position", "purpose", "iss", "aud", "iat", "exp"], "strict_aud": True})
            if claims["sub"] != str(user.id) or claims["role"] != user.role or claims["scope"] != scope or claims["purpose"] != "ticket-list":
                raise ValueError("Cursor scope mismatch")
            last_time = datetime.fromisoformat(claims["position"]["created_at"])
            if last_time.tzinfo is None:
                raise ValueError("Cursor timestamp must include timezone")
            last_id = UUID(claims["position"]["id"])
        except (jwt.InvalidTokenError, ValueError, KeyError, TypeError, AttributeError):
            raise ApiError(422, "invalid_cursor", "The pagination cursor has expired or does not match the current filters or identity") from None
        statement = statement.where(tuple_(Ticket.created_at, Ticket.id) < (last_time, last_id))
    rows = list(session.scalars(statement.order_by(Ticket.created_at.desc(), Ticket.id.desc()).limit(query.limit + 1)))
    page = rows[:query.limit]
    cursor = None
    if len(rows) > query.limit:
        last = page[-1]
        now = datetime.now(timezone.utc)
        cursor = jwt.encode({
            "sub": str(user.id), "role": user.role, "scope": scope, "purpose": "ticket-list",
            "position": {"created_at": last.created_at.isoformat(), "id": str(last.id)},
            "iss": settings.jwt_issuer, "aud": audience, "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_minutes),
        }, secret, algorithm="HS256")
    return TicketPage(items=[TicketSummary.model_validate(row) for row in page], next_cursor=cursor)
