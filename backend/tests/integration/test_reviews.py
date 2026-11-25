from uuid import uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from supportops.errors import ApiError
from supportops.generation import MockGeneration
from supportops.jobs import execute_job
from supportops.models import AnalysisJob, Ticket, TicketMessage, User
from supportops.reviews import ReviewInput, get_suggestion, review
from supportops.seed import synthetic_id
from test_citations import prepared, setup_source, enqueue

pytestmark = pytest.mark.integration


def completed(engine, with_evidence=True):
    if with_evidence:
        setup_source(engine)
    claim = enqueue(engine)
    assert execute_job(engine, *claim, MockGeneration())
    return claim[0]


def test_accepted_review_is_atomic_and_replay_does_not_duplicate(prepared):
    job_id = completed(prepared)
    actor_id = synthetic_id("agent-a")
    with Session(prepared) as session, session.begin():
        actor = session.get(User, actor_id)
        draft = get_suggestion(session, actor, job_id)
        assert draft["suggestion"]["citations"]
        first = review(session, actor_id, job_id, ReviewInput(expected_version=1, decision="accepted"), "review-1")
        second = review(session, actor_id, job_id, ReviewInput(expected_version=1, decision="accepted"), "review-1")
        assert first == second and first.body["ticket_version"] == 2
        assert session.scalar(select(func.count()).select_from(TicketMessage)) == 1
    with Session(prepared) as session, session.begin():
        with pytest.raises(ApiError) as error:
            review(session, actor_id, job_id, ReviewInput(expected_version=2, decision="accepted"), "another")
        assert error.value.status_code == 409
        assert session.scalar(select(func.count()).select_from(TicketMessage)) == 1


def test_no_evidence_requires_independent_human_reply(prepared):
    job_id = completed(prepared, with_evidence=False)
    with Session(prepared) as session, session.begin():
        with pytest.raises(ApiError) as error:
            review(session, synthetic_id("agent-a"), job_id, ReviewInput(expected_version=1, decision="accepted"), "attempt")
        assert error.value.code == "evidence_required"
        result = review(session, synthetic_id("agent-a"), job_id, ReviewInput(expected_version=1, decision="rejected"), "reject")
        assert result.body["message_id"] is None
        assert session.scalar(select(func.count()).select_from(TicketMessage)) == 0


def test_stale_source_and_reassignment_cannot_leak_or_publish(prepared):
    from supportops.models import KnowledgeArticle
    job_id = completed(prepared)
    with Session(prepared) as session, session.begin():
        session.execute(update(KnowledgeArticle).values(archived=True))
        with pytest.raises(ApiError) as error:
            get_suggestion(session, session.get(User, synthetic_id("agent-a")), job_id)
        assert error.value.status_code == 409
        with pytest.raises(ApiError):
            review(session, synthetic_id("agent-a"), job_id, ReviewInput(expected_version=1, decision="edited", edited_body="Edited"), "edit")
        assert session.scalar(select(func.count()).select_from(TicketMessage)) == 0
    with Session(prepared) as session, session.begin():
        session.execute(update(Ticket).where(Ticket.id == synthetic_id("ticket-1")).values(assignee_id=synthetic_id("agent-b")))
        with pytest.raises(ApiError) as error:
            get_suggestion(session, session.get(User, synthetic_id("agent-a")), job_id)
        assert error.value.status_code == 404


def accepted_then_archived(engine):
    from supportops.models import KnowledgeArticle
    job_id = completed(engine)
    with Session(engine) as session, session.begin():
        receipt = review(session, synthetic_id("agent-a"), job_id, ReviewInput(expected_version=1, decision="accepted"), "sent-review")
    with Session(engine) as session, session.begin():
        session.execute(update(KnowledgeArticle).values(archived=True))
    return job_id, receipt


def test_completed_review_replays_after_cited_source_is_archived(prepared):
    job_id, receipt = accepted_then_archived(prepared)
    with Session(prepared) as session, session.begin():
        replay = review(session, synthetic_id("agent-a"), job_id, ReviewInput(expected_version=1, decision="accepted"), "sent-review")
        assert replay == receipt and replay.body["message_id"] is not None
        assert session.scalar(select(func.count()).select_from(TicketMessage)) == 1


def test_new_review_key_after_archive_is_still_stale_and_leaves_no_claim(prepared):
    from supportops.models import IdempotencyRecord
    job_id, _ = accepted_then_archived(prepared)
    with pytest.raises(ApiError) as error:
        with Session(prepared) as session, session.begin():
            review(session, synthetic_id("agent-a"), job_id, ReviewInput(expected_version=2, decision="accepted"), "new-review")
    assert error.value.code == "stale_suggestion"
    with Session(prepared) as session:
        assert session.scalar(select(func.count()).select_from(TicketMessage)) == 1
        assert session.scalar(select(func.count()).select_from(IdempotencyRecord).where(IdempotencyRecord.key == "new-review")) == 0


def test_replay_still_requires_current_assignment_and_staff_role(prepared):
    job_id, _ = accepted_then_archived(prepared)
    accepted = ReviewInput(expected_version=1, decision="accepted")
    with Session(prepared) as session, session.begin():
        session.execute(update(Ticket).where(Ticket.id == synthetic_id("ticket-1")).values(assignee_id=synthetic_id("agent-b")))
        with pytest.raises(ApiError) as error:
            review(session, synthetic_id("agent-a"), job_id, accepted, "sent-review")
        assert error.value.status_code == 404
    with Session(prepared) as session, session.begin():
        session.execute(update(User).where(User.id == synthetic_id("agent-a")).values(role="requester"))
        with pytest.raises(ApiError) as error:
            review(session, synthetic_id("agent-a"), job_id, accepted, "sent-review")
        assert error.value.status_code == 403


def test_legacy_results_require_reanalysis(prepared):
    job_id = completed(prepared, with_evidence=False)
    with Session(prepared) as session, session.begin():
        session.execute(update(AnalysisJob).where(AnalysisJob.id == job_id).values(validation_version=None))
        with pytest.raises(ApiError) as error:
            get_suggestion(session, session.get(User, synthetic_id("agent-a")), job_id)
        assert error.value.code == "suggestion_unavailable"


def test_edited_reply_and_transaction_rollback(prepared):
    from sqlalchemy import event
    job_id = completed(prepared)
    def fail_audit(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO audit_events"):
            raise RuntimeError("synthetic failure")
    event.listen(prepared, "before_cursor_execute", fail_audit)
    try:
        with pytest.raises(RuntimeError):
            with Session(prepared) as session, session.begin():
                review(session, synthetic_id("agent-a"), job_id, ReviewInput(expected_version=1, decision="edited", edited_body="Reviewed response"), "retry")
    finally:
        event.remove(prepared, "before_cursor_execute", fail_audit)
    with Session(prepared) as session, session.begin():
        assert session.scalar(select(func.count()).select_from(TicketMessage)) == 0
        assert session.get(AnalysisJob, job_id).review_decision is None
        assert session.get(Ticket, synthetic_id("ticket-1")).version == 1
        response = review(session, synthetic_id("agent-a"), job_id, ReviewInput(expected_version=1, decision="edited", edited_body="Reviewed response"), "retry")
        assert response.body["decision"] == "edited"
        assert session.scalar(select(TicketMessage.body)) == "Reviewed response"


def test_review_http_route_requires_staff_and_replays(prepared):
    import asyncio
    import httpx
    from supportops.config import Settings
    from supportops.main import create_app
    from supportops.security import issue_token

    job_id = completed(prepared)
    settings = Settings(jwt_secret="test-secret-" * 5)
    app = create_app(settings, engine=prepared)
    async def exercise():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            agent = issue_token(synthetic_id("agent-a"), settings)
            requester = issue_token(synthetic_id("requester-a"), settings)
            auth = {"Authorization": f"Bearer {agent}", "Idempotency-Key": "http-review"}
            path = f"/api/suggestions/{job_id}/review"
            assert (await client.get(f"/api/analysis-jobs/{job_id}/suggestion", headers={"Authorization": f"Bearer {requester}"})).status_code == 403
            assert (await client.get(f"/api/analysis-jobs/{job_id}/suggestion", headers=auth)).status_code == 200
            payload = {"expected_version": 1, "decision": "edited", "edited_body": "Human reviewed response"}
            first = await client.post(path, headers=auth, json=payload)
            replay = await client.post(path, headers=auth, json=payload)
            assert first.status_code == replay.status_code == 200 and first.json() == replay.json()
    asyncio.run(exercise())
