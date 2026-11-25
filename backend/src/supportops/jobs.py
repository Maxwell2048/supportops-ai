"""Analysis job creation and lease-fenced execution."""
from datetime import timedelta
import json
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from supportops.dependencies import visible_ticket
from supportops.errors import ApiError
from supportops.generation import GenerationError, GenerationFailure, MockGeneration, OllamaGeneration, Suggestion
from supportops.idempotency import claim, finish
from supportops.models import AnalysisJob, User
from supportops import agent_tools
from supportops.citations import InvalidCitation, lock_current_sources, validate_citations
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


def list_jobs(session, actor, ticket_id):
    if actor.role not in {"agent", "manager"}:
        raise ApiError(403, "forbidden", "Your current role cannot use this feature")
    visible_ticket(session, actor, ticket_id)
    rows = session.scalars(select(AnalysisJob).where(AnalysisJob.ticket_id == ticket_id)
        .order_by(AnalysisJob.created_at.desc(), AnalysisJob.id.desc()).limit(20))
    return [{"job_id": str(job.id), "status": job.status, "attempts": job.attempts,
             "error_code": job.error_code, "review_decision": job.review_decision} for job in rows]


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


def execute_job(engine, job_id, token, provider, *, loop="handwritten"):
    # Resolved before any job work so an unknown loop is a configuration error, not a job failure.
    gather = agent_tools.gatherer(loop)
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
            ticket_text = (ticket.title + "\n" + ticket.body)[:10000]
            title = ticket.title[:500]
        except ApiError:
            return finish_job(engine, job_id, token, error="retrieval_or_access_unavailable")
    if isinstance(provider, OllamaGeneration):
        provider_info = ("ollama", provider.model, provider.digest)
    elif isinstance(provider, MockGeneration):
        provider_info = ("mock", None, None)
    else:
        provider_info = ("custom", None, None)
    trace = []
    try:
        # Each tool call renews the lease and re-checks current access in its own transaction.
        gathered = gather(engine, job_id, token, provider, ticket_text, title)
        hits, trace = gathered.hits, gathered.trace
        if not hits:
            handoff = Suggestion(category="other", suggested_priority="normal",
                reply_draft="A support agent will review your request.", citations=[],
                human_verification=["No relevant published knowledge was found. Review this request manually."])
            return finish_job(engine, job_id, token, result=handoff.model_dump(mode="json"), validated=True,
                              provider_info=("none", None, None), tool_trace=trace)
        evidence = [json.dumps({"chunk_id": str(hit.chunk_id), "version_id": str(hit.version_id), "text": hit.text}) for hit in hits]
        extra = {"context": gathered.context} if getattr(provider, "plan", None) and gathered.context else {}
        result = Suggestion.model_validate(provider.generate(ticket_text, evidence, **extra))
        validate_citations(result, hits)
        return finish_job(engine, job_id, token, result=result.model_dump(mode="json"), hits=hits, validated=True,
                          provider_info=provider_info, tool_trace=trace)
    except agent_tools.ToolStopped as stop:
        if stop.code == "lease_lost":
            return False
        return finish_job(engine, job_id, token, error=stop.code, provider_info=provider_info, tool_trace=stop.trace)
    except InvalidCitation:
        return finish_job(engine, job_id, token, error="invalid_citation", provider_info=provider_info, tool_trace=trace)
    except (ValidationError, TypeError, ValueError):
        return finish_job(engine, job_id, token, error="invalid_output", provider_info=provider_info, tool_trace=trace)
    except GenerationError as error:
        transient = error.kind in {GenerationFailure.TIMEOUT, GenerationFailure.UNAVAILABLE}
        return finish_job(engine, job_id, token, error=error.kind.value, transient=transient, provider_info=provider_info, tool_trace=trace)


def finish_job(engine, job_id, token, *, result=None, error=None, transient=False, hits=(), validated=False, provider_info=None, tool_trace=None):
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
        if provider_info:
            job.generation_provider, job.generation_model, job.generation_digest = provider_info
        job.tool_trace = tool_trace or None
        job.lease_token = job.lease_expires_at = None
        job.updated_at = now
        return True
