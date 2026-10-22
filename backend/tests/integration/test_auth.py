import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import jwt
import pytest
from sqlalchemy import update

from supportops.config import Settings
from supportops.demo_accounts import activate_demo_accounts
from supportops.dependencies import get_session
from supportops.main import create_app
from supportops.models import Ticket, TicketMessage, User
from supportops.rate_limit import LoginLimiter
from supportops.security import hash_password, issue_token, verify_password
from supportops.seed import seed, synthetic_id


pytestmark = pytest.mark.integration
PASSWORD = "synthetic-test-password-123"
SECRET = "integration-only-signing-secret-" * 2


@pytest.fixture(scope="module")
def encoded_password():
    return hash_password(PASSWORD)


@pytest.fixture
def auth_app(db_session, pg_engine, encoded_password):
    # Fixture setup only: these writes are not the unimplemented business service.
    seed(db_session)
    db_session.execute(update(User).values(active=True, password_hash=encoded_password))
    ticket_id = synthetic_id("ticket-1")
    db_session.execute(update(Ticket).where(Ticket.id == ticket_id).values(assignee_id=synthetic_id("agent-a")))
    db_session.add_all([
        TicketMessage(ticket_id=ticket_id, author_id=synthetic_id("agent-a"), visibility="public", body="Public progress update"),
        TicketMessage(ticket_id=ticket_id, author_id=synthetic_id("agent-a"), visibility="internal", body="Internal-only diagnostic details"),
    ])
    db_session.flush()
    app = create_app(Settings(jwt_secret=SECRET), engine=pg_engine)

    def isolated_session():
        yield db_session

    app.dependency_overrides[get_session] = isolated_session
    return app


def run(app, scenario):
    async def execute():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await scenario(client)
    return asyncio.run(execute())


def authorization(app, label):
    return {"Authorization": "Bearer " + issue_token(synthetic_id(label), app.state.settings)}


def test_login_then_me_returns_only_public_identity(auth_app):
    async def scenario(client):
        response = await client.post("/api/auth/login", json={"email": " Requester-A@Example.Invalid ", "password": PASSWORD})
        assert response.status_code == 200
        payload = response.json()
        assert set(payload) == {"access_token", "token_type", "expires_in"}
        assert payload["expires_in"] == 900 and payload["token_type"] == "bearer"
        assert response.headers["cache-control"] == "no-store"
        me = await client.get("/api/me", headers={"Authorization": "Bearer " + payload["access_token"]})
        assert me.status_code == 200
        assert me.json() == {"id": str(synthetic_id("requester-a")), "email": "requester-a@example.invalid", "role": "requester"}
        assert "password" not in me.text and "hash" not in me.text
    run(auth_app, scenario)


def test_unknown_wrong_password_and_disabled_login_have_same_error(auth_app, db_session):
    async def scenario(client):
        db_session.execute(update(User).where(User.id == synthetic_id("requester-b")).values(active=False))
        for email, password in [
            ("missing@example.invalid", PASSWORD), ("requester-a@example.invalid", "wrong"),
            ("requester-b@example.invalid", PASSWORD),
        ]:
            response = await client.post("/api/auth/login", json={"email": email, "password": password})
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "invalid_credentials"
            assert response.json()["error"]["message"] == "Incorrect email or password"
            assert response.headers["www-authenticate"] == "Bearer"
    run(auth_app, scenario)


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer malformed"}, {"Authorization": "Bearer " + "a" * 4097}])
def test_missing_or_invalid_credentials_are_401(auth_app, headers):
    async def scenario(client):
        response = await client.get("/api/me", headers=headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "invalid_session"
        assert response.headers["x-request-id"] == response.json()["error"]["request_id"]
    run(auth_app, scenario)


@pytest.mark.parametrize("kind", ["expired", "wrong_signature", "wrong_issuer", "wrong_audience", "missing_user"])
def test_invalid_signed_sessions_are_rejected_at_api_boundary(auth_app, kind):
    settings = auth_app.state.settings
    token = issue_token(synthetic_id("requester-a"), settings)
    claims = jwt.decode(token, SECRET, algorithms=["HS256"], audience=settings.jwt_audience)
    key = SECRET
    if kind == "expired":
        claims["iat"] = int((datetime.now(timezone.utc) - timedelta(hours=1)).timestamp())
        claims["nbf"] = claims["iat"]
        claims["exp"] = claims["iat"] + 60
    elif kind == "wrong_signature":
        key = "wrong-test-signing-secret-" * 3
    elif kind == "wrong_issuer":
        claims["iss"] = "other-api"
    elif kind == "wrong_audience":
        claims["aud"] = "other-client"
    elif kind == "missing_user":
        claims["sub"] = str(uuid4())
    headers = {"Authorization": "Bearer " + jwt.encode(claims, key, algorithm="HS256")}
    async def scenario(client):
        response = await client.get("/api/me", headers=headers)
        assert response.status_code == 401
    run(auth_app, scenario)


def test_disabled_account_loses_access_with_existing_token(auth_app, db_session):
    headers = authorization(auth_app, "requester-a")
    async def scenario(client):
        assert (await client.get("/api/me", headers=headers)).status_code == 200
        db_session.execute(update(User).where(User.id == synthetic_id("requester-a")).values(active=False))
        assert (await client.get("/api/me", headers=headers)).status_code == 401
    run(auth_app, scenario)


@pytest.mark.parametrize("label,status,staff", [
    ("requester-a", 200, False), ("requester-b", 404, False),
    ("agent-a", 200, True), ("agent-b", 404, True), ("manager", 200, True),
])
def test_ticket_access_and_internal_fields_follow_current_role(auth_app, label, status, staff):
    async def scenario(client):
        response = await client.get(f"/api/tickets/{synthetic_id('ticket-1')}", headers=authorization(auth_app, label))
        assert response.status_code == status
        if status == 404:
            assert "Cannot sign in" not in response.text and "internal" not in response.text
            return
        payload = response.json()
        assert "password_hash" not in response.text
        if staff:
            assert {message["visibility"] for message in payload["messages"]} == {"public", "internal"}
            assert len(payload["events"]) == 1
        else:
            assert "events" not in payload
            assert [message["visibility"] for message in payload["messages"]] == ["public"]
            assert "Internal-only" not in response.text
    run(auth_app, scenario)


@pytest.mark.parametrize("label,status", [("requester-a", 403), ("agent-a", 200), ("agent-b", 404), ("manager", 200)])
def test_events_require_staff_role_and_ticket_scope(auth_app, label, status):
    async def scenario(client):
        response = await client.get(f"/api/tickets/{synthetic_id('ticket-1')}/events", headers=authorization(auth_app, label))
        assert response.status_code == status
    run(auth_app, scenario)


def test_reassignment_immediately_revokes_previous_agent_read_access(auth_app, db_session):
    async def scenario(client):
        path = f"/api/tickets/{synthetic_id('ticket-1')}"
        assert (await client.get(path, headers=authorization(auth_app, "agent-a"))).status_code == 200
        db_session.execute(update(Ticket).where(Ticket.id == synthetic_id("ticket-1")).values(assignee_id=synthetic_id("agent-b")))
        assert (await client.get(path, headers=authorization(auth_app, "agent-a"))).status_code == 404
        assert (await client.get(path, headers=authorization(auth_app, "agent-b"))).status_code == 200
    run(auth_app, scenario)


def test_role_claim_is_ignored_and_current_database_role_is_used(auth_app, db_session):
    settings = auth_app.state.settings
    claims = jwt.decode(issue_token(synthetic_id("requester-a"), settings), SECRET, algorithms=["HS256"], audience=settings.jwt_audience)
    claims["role"] = "manager"
    headers = {"Authorization": "Bearer " + jwt.encode(claims, SECRET, algorithm="HS256")}
    async def scenario(client):
        assert (await client.get("/api/me", headers=headers)).json()["role"] == "requester"
        path = f"/api/tickets/{synthetic_id('ticket-1')}/events"
        assert (await client.get(path, headers=headers)).status_code == 403
        db_session.execute(update(User).where(User.id == synthetic_id("requester-a")).values(role="agent"))
        assert (await client.get("/api/me", headers=headers)).json()["role"] == "agent"
    run(auth_app, scenario)


def test_validation_never_reflects_password_and_rejects_role_injection(auth_app):
    async def scenario(client):
        for extra in [{"role": "manager"}, {"requester_id": str(uuid4())}, {"author_id": str(uuid4())}]:
            password = "do-not-reflect-this-private-password"
            response = await client.post("/api/auth/login", json={"email": "requester-a@example.invalid", "password": password, **extra})
            assert response.status_code == 422
            assert password not in response.text
            assert response.json()["error"]["code"] == "validation_error"
    run(auth_app, scenario)


def test_http_login_limit_and_forwarded_header_cannot_bypass_it(auth_app):
    auth_app.state.login_limiter = LoginLimiter(email_limit=10, ip_limit=2)
    async def scenario(client):
        for index in range(2):
            payload = {"email": f"missing-{index}@example.invalid", "password": "wrong"}
            assert (await client.post("/api/auth/login", json=payload, headers={"X-Forwarded-For": f"1.2.3.{index}"})).status_code == 401
        payload = {"email": "requester-a@example.invalid", "password": "wrong"}
        response = await client.post("/api/auth/login", json=payload, headers={"X-Forwarded-For": "8.8.8.8"})
        assert response.status_code == 429
        assert response.headers["retry-after"] == "60"
    run(auth_app, scenario)


def test_missing_auth_configuration_is_not_ready_and_cannot_issue_token(auth_app):
    unconfigured = create_app(Settings(), engine=auth_app.state.engine)
    unconfigured.dependency_overrides.update(auth_app.dependency_overrides)
    async def scenario(client):
        readiness = await client.get("/ready")
        assert readiness.status_code == 503 and readiness.json()["reason"] == "auth_not_configured"
        response = await client.post("/api/auth/login", json={"email": "requester-a@example.invalid", "password": PASSWORD})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "auth_not_configured"
    run(unconfigured, scenario)


def test_demo_activation_does_not_reset_password_or_reactivate_account(db_session):
    seed(db_session)
    assert activate_demo_accounts(db_session, PASSWORD) == 5
    db_session.flush()
    user = db_session.get(User, synthetic_id("requester-a"))
    old_hash = user.password_hash
    user.active = False
    assert activate_demo_accounts(db_session, "different-synthetic-password") == 0
    assert not user.active and user.password_hash == old_hash
    assert verify_password(PASSWORD, user.password_hash)
    assert not verify_password("different-synthetic-password", user.password_hash)
