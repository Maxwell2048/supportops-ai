from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest

from supportops.config import Settings
from supportops.errors import ApiError
from supportops.rate_limit import LoginLimiter
from supportops.security import decode_subject, hash_password, issue_token, verify_password


SECRET = "test-only-secret-not-for-deployment-" * 2


def test_password_is_salted_argon2_and_wrong_password_is_rejected():
    password = "test-only-password-123"
    first, second = hash_password(password), hash_password(password)
    assert first != second and first.startswith("$argon2id$")
    assert password not in first
    assert verify_password(password, first)
    assert not verify_password("incorrect", first)
    assert not verify_password(password, "!login-disabled-until-S06")
    assert not verify_password(password, None)


def test_token_contains_only_identity_and_required_claims():
    user_id = uuid4()
    settings = Settings(jwt_secret=SECRET)
    token = issue_token(user_id, settings)
    assert decode_subject(token, settings) == user_id
    claims = jwt.decode(token, SECRET, algorithms=["HS256"], audience=settings.jwt_audience, issuer=settings.jwt_issuer)
    assert set(claims) == {"sub", "jti", "iss", "aud", "iat", "nbf", "exp"}
    assert claims["exp"] - claims["iat"] == 900


@pytest.mark.parametrize("change", [
    {"iss": "wrong"}, {"aud": "wrong"}, {"aud": ["supportops-web", "other"]},
    {"exp": 1}, {"sub": "not-a-uuid"}, {"nbf": 9999999999}, {"iat": 9999999999},
])
def test_invalid_claims_are_rejected(change):
    settings = Settings(jwt_secret=SECRET)
    now = datetime.now(timezone.utc)
    claims = {"sub": str(uuid4()), "jti": str(uuid4()), "iss": settings.jwt_issuer, "aud": settings.jwt_audience,
              "iat": now, "nbf": now, "exp": now + timedelta(minutes=15), **change}
    with pytest.raises(ApiError) as error:
        decode_subject(jwt.encode(claims, SECRET, algorithm="HS256"), settings)
    assert error.value.status_code == 401


@pytest.mark.parametrize("missing", ["sub", "jti", "iss", "aud", "iat", "nbf", "exp"])
def test_missing_required_claims_are_rejected(missing):
    settings = Settings(jwt_secret=SECRET)
    claims = jwt.decode(issue_token(uuid4(), settings), SECRET, algorithms=["HS256"], audience=settings.jwt_audience)
    del claims[missing]
    with pytest.raises(ApiError):
        decode_subject(jwt.encode(claims, SECRET, algorithm="HS256"), settings)


@pytest.mark.parametrize("algorithm,key", [("HS384", SECRET), ("HS256", "other-test-key-" * 5), ("none", None)])
def test_disallowed_algorithm_and_signature_are_rejected(algorithm, key):
    settings = Settings(jwt_secret=SECRET)
    claims = jwt.decode(issue_token(uuid4(), settings), SECRET, algorithms=["HS256"], audience=settings.jwt_audience)
    with pytest.raises(ApiError):
        decode_subject(jwt.encode(claims, key, algorithm=algorithm), settings)


def test_limiter_blocks_account_and_ip_and_recovers_after_window():
    now = [0.0]
    limiter = LoginLimiter(email_limit=2, ip_limit=3, window_seconds=60, clock=lambda: now[0])
    limiter.check("a@example.invalid", "ip1")
    limiter.check("a@example.invalid", "ip2")
    with pytest.raises(ApiError) as error:
        limiter.check("a@example.invalid", "ip3")
    assert error.value.status_code == 429
    limiter.check("b@example.invalid", "ip1")
    limiter.check("c@example.invalid", "ip1")
    with pytest.raises(ApiError):
        limiter.check("d@example.invalid", "ip1")
    now[0] = 61
    limiter.check("a@example.invalid", "ip1")


def test_limiter_does_not_evict_live_keys_to_allow_bypass():
    limiter = LoginLimiter(max_keys=2)
    limiter.check("a@example.invalid", "ip1")
    with pytest.raises(ApiError):
        limiter.check("b@example.invalid", "ip2")


@pytest.mark.parametrize("kwargs", [{"jwt_secret": "short"}, {"access_token_minutes": 0}, {"access_token_minutes": 31}, {"jwt_issuer": ""}, {"jwt_audience": ""}])
def test_invalid_auth_configuration_fails_closed(kwargs):
    with pytest.raises(ValueError):
        Settings(**kwargs)


def test_settings_repr_does_not_contain_signing_secret():
    assert SECRET not in repr(Settings(jwt_secret=SECRET))
