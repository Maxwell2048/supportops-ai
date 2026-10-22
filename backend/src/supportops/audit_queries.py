"""Manager-only, bounded audit queries with identity/filter-bound keyset cursors."""
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from sqlalchemy import select, tuple_

from supportops.errors import ApiError
from supportops.idempotency import canonical_hash
from supportops.models import AuditEvent
from supportops.schemas import AuditPage, AuditQuery, AuditResponse
from supportops.security import require_auth_config


def list_audit_events(session, user, query: AuditQuery, settings):
    # This check deliberately precedes all audit reads and cursor validation.
    if user.role != 'manager':
        raise ApiError(403, 'forbidden', 'Only managers can query audit records')
    scope = canonical_hash(query.model_dump(mode='json', exclude={'cursor'}))
    statement = select(AuditEvent)
    for name in ('resource_type', 'resource_id', 'actor_id', 'request_id', 'action'):
        value = getattr(query, name)
        if value is not None:
            statement = statement.where(getattr(AuditEvent, name) == value)
    secret = require_auth_config(settings)
    audience = settings.jwt_audience + ':audit-list'
    if query.cursor:
        try:
            claims = jwt.decode(query.cursor, secret, algorithms=['HS256'], issuer=settings.jwt_issuer,
                audience=audience, options={'require': ['sub', 'scope', 'position', 'purpose', 'iss', 'aud', 'iat', 'exp'], 'strict_aud': True})
            if claims['sub'] != str(user.id) or claims['scope'] != scope or claims['purpose'] != 'audit-list':
                raise ValueError('Cursor scope mismatch')
            last_time = datetime.fromisoformat(claims['position']['created_at'])
            if last_time.tzinfo is None:
                raise ValueError('Timezone missing')
            last_id = UUID(claims['position']['id'])
        except (jwt.InvalidTokenError, ValueError, KeyError, TypeError, AttributeError):
            raise ApiError(422, 'invalid_cursor', 'The audit cursor has expired or does not match the current filters or identity') from None
        statement = statement.where(tuple_(AuditEvent.created_at, AuditEvent.id) < (last_time, last_id))
    rows = list(session.scalars(statement.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(query.limit + 1)))
    page = rows[:query.limit]
    cursor = None
    if len(rows) > query.limit:
        last, now = page[-1], datetime.now(timezone.utc)
        cursor = jwt.encode({'sub': str(user.id), 'scope': scope, 'purpose': 'audit-list',
            'position': {'created_at': last.created_at.isoformat(), 'id': str(last.id)},
            'iss': settings.jwt_issuer, 'aud': audience, 'iat': now,
            'exp': now + timedelta(minutes=settings.access_token_minutes)}, secret, algorithm='HS256')
    return AuditPage(items=[AuditResponse.model_validate(row) for row in page], next_cursor=cursor)
