from pathlib import Path
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from supportops.jobs import JobCreate, claim_job, create_job, execute_job, finish_job, read_job, renew_lease
from supportops.generation import MockGeneration
from supportops.errors import ApiError
from supportops.models import AnalysisJob, Ticket, User
from supportops.seed import seed, synthetic_id

pytestmark = pytest.mark.integration


@pytest.fixture
def prepared(pg_engine):
    with Session(pg_engine) as session, session.begin():
        session.execute(delete(AnalysisJob))
        seed(session)
        session.execute(update(User).values(active=True))
        session.execute(update(Ticket).where(Ticket.id == synthetic_id("ticket-1")).values(assignee_id=synthetic_id("agent-a")))
    return pg_engine


def test_job_idempotency_and_current_permissions(prepared):
    with Session(prepared) as session, session.begin():
        payload = JobCreate(expected_version=1)
        first = create_job(session, synthetic_id("agent-a"), synthetic_id("ticket-1"), payload, "same")
        second = create_job(session, synthetic_id("agent-a"), synthetic_id("ticket-1"), payload, "same")
        assert first == second and first.status == 202
        assert session.scalar(select(func.count()).select_from(AnalysisJob)) == 1
        with pytest.raises(ApiError) as error:
            create_job(session, synthetic_id("agent-a"), synthetic_id("ticket-1"), JobCreate(expected_version=2), "same")
        assert error.value.status_code == 409
        job_id = first.body["job_id"]
    with Session(prepared) as session, session.begin():
        session.execute(update(Ticket).where(Ticket.id == synthetic_id("ticket-1")).values(assignee_id=synthetic_id("agent-b")))
        actor = session.get(User, synthetic_id("agent-a"))
        with pytest.raises(ApiError) as error:
            read_job(session, actor, job_id)
        assert error.value.status_code == 404


def test_expired_lease_cannot_commit_and_retry_completes(prepared):
    with Session(prepared) as session, session.begin():
        job = AnalysisJob(id=uuid4(), ticket_id=synthetic_id("ticket-1"), requester_id=synthetic_id("agent-a"), ticket_version=1)
        session.add(job)
        job_id = job.id
    with Session(prepared) as session, session.begin():
        first = claim_job(session)
    with Session(prepared) as session, session.begin():
        now = session.scalar(select(func.clock_timestamp()))
        session.execute(update(AnalysisJob).where(AnalysisJob.id == job_id).values(lease_expires_at=now - timedelta(seconds=1)))
    with Session(prepared) as session, session.begin():
        second = claim_job(session)
    assert first[0] == second[0] == job_id and first[1] != second[1]
    assert not finish_job(prepared, *first, result={"stale": True})
    assert execute_job(prepared, *second, MockGeneration())
    with Session(prepared) as session:
        job = session.get(AnalysisJob, job_id)
        assert job.status == "succeeded" and job.attempts == 2
        assert job.result["category"] == "other"


def test_worker_process_resumes_expired_job(prepared):
    import os
    import subprocess
    import sys

    with Session(prepared) as session, session.begin():
        job = AnalysisJob(id=uuid4(), ticket_id=synthetic_id("ticket-1"), requester_id=synthetic_id("agent-a"), ticket_version=1)
        session.add(job)
        job_id = job.id
        schema = session.scalar(select(func.current_schema()))
    with Session(prepared) as session, session.begin():
        old = claim_job(session)
        now = session.scalar(select(func.clock_timestamp()))
        session.execute(update(AnalysisJob).where(AnalysisJob.id == job_id).values(lease_expires_at=now - timedelta(seconds=1)))
    env = os.environ.copy()
    env["DATABASE_URL"] = prepared.url.render_as_string(hide_password=False)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[2] / "src")
    env["PGOPTIONS"] = f"-csearch_path={schema},public"
    code = "import os, sqlalchemy; import supportops.job_worker as w; w.make_engine = lambda url: sqlalchemy.create_engine(url, connect_args={'options': os.environ['PGOPTIONS']}, hide_parameters=True); w.main()"
    run = subprocess.run([sys.executable, "-c", code, "--once"], env=env, capture_output=True, text=True, timeout=30)
    assert run.returncode == 0, run.stderr
    assert not finish_job(prepared, *old, result={})
    with Session(prepared) as session:
        job = session.get(AnalysisJob, job_id)
        assert job.status == "succeeded" and job.attempts == 2


def test_retries_and_exhaustion(prepared):
    with Session(prepared) as session, session.begin():
        job = AnalysisJob(id=uuid4(), ticket_id=synthetic_id("ticket-1"), requester_id=synthetic_id("agent-a"), ticket_version=1)
        session.add(job)
        job_id = job.id
    for attempt in range(1, 4):
        with Session(prepared) as session, session.begin():
            claim = claim_job(session)
        assert finish_job(prepared, *claim, error="timeout", transient=True)
        with Session(prepared) as session, session.begin():
            job = session.get(AnalysisJob, job_id)
            assert job.status == ("queued" if attempt < 3 else "failed")
            if attempt < 3:
                job.next_attempt_at = session.scalar(select(func.clock_timestamp())) - timedelta(seconds=1)


def test_concurrent_claim_skips_locked_job(prepared):
    with Session(prepared) as session, session.begin():
        session.add(AnalysisJob(id=uuid4(), ticket_id=synthetic_id("ticket-1"), requester_id=synthetic_id("agent-a"), ticket_version=1))
    with Session(prepared) as first, first.begin():
        claimed = claim_job(first)
        with Session(prepared) as second, second.begin():
            assert claim_job(second) is None
    assert claimed is not None


def test_http_create_read_and_role_checks(prepared):
    import asyncio
    import httpx
    from supportops.config import Settings
    from supportops.main import create_app
    from supportops.security import issue_token

    settings = Settings(jwt_secret="test-secret-" * 5)
    app = create_app(settings, engine=prepared)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            token = issue_token(synthetic_id("agent-a"), settings)
            headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": "http-job"}
            path = f"/api/tickets/{synthetic_id('ticket-1')}/analysis-jobs"
            first = await client.post(path, headers=headers, json={"expected_version": 1})
            replay = await client.post(path, headers=headers, json={"expected_version": 1})
            assert first.status_code == replay.status_code == 202 and first.json() == replay.json()
            job_path = "/api/analysis-jobs/" + first.json()["job_id"]
            assert (await client.get(job_path, headers=headers)).json()["status"] == "queued"
            requester = issue_token(synthetic_id("requester-a"), settings)
            assert (await client.get(job_path, headers={"Authorization": f"Bearer {requester}"})).status_code == 403
    asyncio.run(scenario())


def test_renewal_requires_live_matching_token(prepared):
    with Session(prepared) as session, session.begin():
        session.add(AnalysisJob(id=uuid4(), ticket_id=synthetic_id("ticket-1"), requester_id=synthetic_id("agent-a"), ticket_version=1))
    with Session(prepared) as session, session.begin():
        job_id, token = claim_job(session)
    with Session(prepared) as session, session.begin():
        assert not renew_lease(session, job_id, uuid4())
        assert renew_lease(session, job_id, token)
        now = session.scalar(select(func.clock_timestamp()))
        session.execute(update(AnalysisJob).where(AnalysisJob.id == job_id).values(lease_expires_at=now - timedelta(seconds=1)))
    with Session(prepared) as session, session.begin():
        assert not renew_lease(session, job_id, token)
