"""Analysis job creation and lease-fenced execution."""
from datetime import timedelta
import json
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from supportops.dependencies import visible_ticket
from supportops.errors import ApiError
from supportops.generation import GenerationError, GenerationFailure, Suggestion
from supportops.idempotency import claim, finish
from supportops.models import AnalysisJob, User
from supportops import retrieval
from supportops.citations import InvalidCitation, lock_current_sources, validate_citations
from supportops.retrieval_schemas import SearchQuery
from supportops.ticket_service import _actor, _version


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_version: int = Field(ge=1)


class JobReceipt(BaseModel):
    job_id: str
    status: str


def create_job(session, actor_id, ticket_id, payload, key):
    actor = _actor(session, actor_id)
    if actor.role not in {"agent", "manager"}:
        raise ApiError(403, "forbidden", "Your current role cannot use this feature")
    ticket = visible_ticket(session, actor, ticket_id, lock=True)
    record, replay = claim(session, actor.id, ticket.id, "analysis_job_create", key, payload)
    if replay:
        return replay
    _version(ticket, payload.expected_version)
    if ticket.archived:
        raise ApiError(409, "ticket_archived", "The ticket is archived")
    job = AnalysisJob(id=uuid4(), ticket_id=ticket.id, requester_id=actor.id, ticket_version=ticket.version)
    session.add(job)
    session.flush()
    return finish(session, record, 202, JobReceipt(job_id=str(job.id), status="queued"))


def read_job(session, actor, job_id):
    if actor.role not in {"agent", "manager"}:
        raise ApiError(403, "forbidden", "Your current role cannot use this feature")
    job = session.get(AnalysisJob, job_id)
    if job is None:
        raise ApiError(404, "not_found", "The job does not exist or is not accessible")
    visible_ticket(session, actor, job.ticket_id)
    return {"job_id": str(job.id), "status": job.status, "attempts": job.attempts, "error_code": job.error_code}


def claim_job(session):
    now = session.scalar(select(func.clock_timestamp()))
    job = session.scalar(select(AnalysisJob).where(or_(
        (AnalysisJob.status == "queued") & (AnalysisJob.next_attempt_at <= now),
        (AnalysisJob.status == "running") & (AnalysisJob.lease_expires_at <= now),
    )).order_by(AnalysisJob.created_at, AnalysisJob.id).with_for_update(skip_locked=True).limit(1))
    if job is None:
        return None
    if job.attempts >= 3:
        job.status, job.error_code = "failed", "attempts_exhausted"
        job.lease_token = job.lease_expires_at = None
        job.updated_at = now
        return None
    job.status = "running"
    job.attempts += 1
    job.lease_token = uuid4()
    job.lease_expires_at = now + timedelta(seconds=180)
    job.updated_at = now
    session.flush()
    return job.id, job.lease_token


def renew_lease(session, job_id, token):
    job = session.scalar(select(AnalysisJob).where(
        AnalysisJob.id == job_id, AnalysisJob.status == "running",
        AnalysisJob.lease_token == token, AnalysisJob.lease_expires_at > func.clock_timestamp(),
    ).with_for_update())
    now = session.scalar(select(func.clock_timestamp()))
    if job is None or job.lease_expires_at <= now:
        return False
    job.lease_expires_at = now + timedelta(seconds=180)
    job.updated_at = now
    return True


def execute_job(engine, job_id, token, provider):
    # Read under current authorization and release the transaction before inference.
    with Session(engine) as session:
        job = session.scalar(select(AnalysisJob).where(
            AnalysisJob.id == job_id, AnalysisJob.status == "running",
            AnalysisJob.lease_token == token, AnalysisJob.lease_expires_at > func.clock_timestamp(),
        ))
        if job is None:
            return False
        actor = session.get(User, job.requester_id) if job else None
        try:
            if not actor or not actor.active or actor.role not in {"agent", "manager"}:
                raise ApiError(403, "forbidden", "Access revoked")
            ticket = visible_ticket(session, actor, job.ticket_id)
            if ticket.version != job.ticket_version or ticket.archived:
                raise ApiError(409, "ticket_changed", "Ticket changed")
            ticket_text = ticket.title + "\n" + ticket.body
            found = retrieval.search(session, actor, SearchQuery(q=ticket.title[:500], mode="keyword"), None)
            if found.indexed_versions < found.available_versions:
                raise ApiError(503, "retrieval_incomplete", "Knowledge indexing is incomplete")
            hits = found.items
        except ApiError:
            return finish_job(engine, job_id, token, error="retrieval_or_access_unavailable")
    if not hits:
        handoff = Suggestion(category="other", suggested_priority="normal",
            reply_draft="A support agent will review your request.", citations=[],
            human_verification=["No relevant published knowledge was found. Review this request manually."])
        return finish_job(engine, job_id, token, result=handoff.model_dump(mode="json"), validated=True)
    try:
        evidence = [json.dumps({"chunk_id": str(hit.chunk_id), "version_id": str(hit.version_id), "text": hit.text}) for hit in hits]
        result = Suggestion.model_validate(provider.generate(ticket_text[:10000], evidence))
        validate_citations(result, hits)
        return finish_job(engine, job_id, token, result=result.model_dump(mode="json"), hits=hits, validated=True)
    except InvalidCitation:
        return finish_job(engine, job_id, token, error="invalid_citation")
    except (ValidationError, TypeError, ValueError):
        return finish_job(engine, job_id, token, error="invalid_output")
    except GenerationError as error:
        transient = error.kind in {GenerationFailure.TIMEOUT, GenerationFailure.UNAVAILABLE}
        return finish_job(engine, job_id, token, error=error.kind.value, transient=transient)


def finish_job(engine, job_id, token, *, result=None, error=None, transient=False, hits=(), validated=False):
    with Session(engine) as session, session.begin():
        now = session.scalar(select(func.clock_timestamp()))
        job = session.scalar(select(AnalysisJob).where(
            AnalysisJob.id == job_id, AnalysisJob.status == "running",
            AnalysisJob.lease_token == token, AnalysisJob.lease_expires_at > func.clock_timestamp(),
        ).with_for_update())
        if job is None:
            return False
        actor = session.scalar(select(User).where(User.id == job.requester_id).with_for_update(read=True))
        try:
            if not actor or not actor.active or actor.role not in {"agent", "manager"}:
                raise ApiError(403, "forbidden", "Access revoked")
            ticket = visible_ticket(session, actor, job.ticket_id, lock=True)
            if ticket.version != job.ticket_version or ticket.archived:
                raise ApiError(409, "ticket_changed", "Ticket changed")
            if hits and not lock_current_sources(session, actor, hits):
                raise ApiError(409, "knowledge_changed", "Knowledge changed")
        except ApiError:
            result, error, transient = None, "access_or_ticket_changed", False
        now = session.scalar(select(func.clock_timestamp()))
        if job.lease_expires_at <= now:
            return False
        if error and transient and job.attempts < 3:
            job.status = "queued"
            job.next_attempt_at = now + timedelta(seconds=10 * job.attempts)
        else:
            job.status = "failed" if error else "succeeded"
        job.error_code = error
        job.result = result if not error else None
        job.validation_version = "s17-v1" if result and not error and validated else None
        job.lease_token = job.lease_expires_at = None
        job.updated_at = now
        return True
