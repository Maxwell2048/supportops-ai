"""Password and token operations delegate to maintained libraries."""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from supportops.config import Settings
from supportops.errors import ApiError


PASSWORDS = PasswordHash.recommended()
DUMMY_HASH = PASSWORDS.hash("synthetic-dummy-password-never-used-to-login")


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 128:
        raise ValueError("Demo passwords must contain 12 to 128 characters")
    return PASSWORDS.hash(password)


def verify_password(password: str, encoded: str | None) -> bool:
    if encoded is None:
        PASSWORDS.verify(password, DUMMY_HASH)
        return False
    try:
        return PASSWORDS.verify(password, encoded)
    except (UnknownHashError, ValueError):
        PASSWORDS.verify(password, DUMMY_HASH)
        return False


def require_auth_config(settings: Settings) -> str:
    if not settings.jwt_secret:
        raise ApiError(503, "auth_not_configured", "Authentication is not configured")
    return settings.jwt_secret


def issue_token(user_id: UUID, settings: Settings) -> str:
    secret = require_auth_config(settings)
    now = datetime.now(timezone.utc)
    return jwt.encode({
        "sub": str(user_id), "jti": str(uuid4()),
        "iss": settings.jwt_issuer, "aud": settings.jwt_audience,
        "iat": now, "nbf": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }, secret, algorithm="HS256")


def invalid_session() -> ApiError:
    return ApiError(401, "invalid_session", "Your session is invalid; please sign in again", {"WWW-Authenticate": "Bearer"})


def decode_subject(token: str, settings: Settings) -> UUID:
    secret = require_auth_config(settings)
    if len(token) > 4096:
        raise invalid_session()
    try:
        claims = jwt.decode(
            token, secret, algorithms=["HS256"],
            issuer=settings.jwt_issuer, audience=settings.jwt_audience,
            options={"require": ["sub", "jti", "iss", "aud", "iat", "nbf", "exp"], "strict_aud": True},
        )
        return UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError):
        raise invalid_session() from None
