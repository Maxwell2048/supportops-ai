"""Human review of validated analysis results."""
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select

from supportops.citations import InvalidCitation, lock_current_sources, validate_citations
from supportops.dependencies import visible_ticket
from supportops.errors import ApiError
from supportops.generation import Suggestion
from supportops.idempotency import claim, finish
from supportops.models import AnalysisJob, KnowledgeChunk, KnowledgeVersion, TicketMessage
from supportops.schemas import BodyText
from supportops.ticket_service import _actor, _event, _update, _version


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(strict=True, gt=0, le=2147483647)
    decision: Literal["accepted", "edited", "rejected"]
    edited_body: BodyText | None = None

    @model_validator(mode="after")
    def validate_decision(self):
        if (self.decision == "edited") != (self.edited_body is not None):
            raise ValueError("Edited decisions require an edited body")
        return self


class ReviewReceipt(BaseModel):
    job_id: UUID
    decision: str
    message_id: UUID | None
    ticket_version: int


def validated_suggestion(session, actor, job):
    if job.status != "succeeded" or job.validation_version != "s17-v1" or not job.result:
        raise ApiError(409, "suggestion_unavailable", "This result must be analyzed again")
    try:
        suggestion = Suggestion.model_validate(job.result)
    except ValidationError:
        raise ApiError(409, "suggestion_unavailable", "This result must be analyzed again") from None
    if suggestion.citations:
        ids = [citation.chunk_id for citation in suggestion.citations]
        rows = session.execute(select(KnowledgeChunk, KnowledgeVersion).join(
            KnowledgeVersion, KnowledgeVersion.id == KnowledgeChunk.version_id).where(KnowledgeChunk.id.in_(ids))).all()
        hits = [SimpleNamespace(chunk_id=chunk.id, version_id=version.id, article_id=version.article_id, text=chunk.content) for chunk, version in rows]
        try:
            validate_citations(suggestion, hits)
            if not lock_current_sources(session, actor, hits):
                raise InvalidCitation()
        except InvalidCitation:
            raise ApiError(409, "stale_suggestion", "Knowledge access or publication changed; analyze again") from None
    return suggestion


def get_suggestion(session, actor, job_id):
    if actor.role not in {"agent", "manager"}:
        raise ApiError(403, "forbidden", "Your current role cannot use this feature")
    job = session.get(AnalysisJob, job_id)
    if job is None:
        raise ApiError(404, "not_found", "The suggestion does not exist or is not accessible")
    ticket = visible_ticket(session, actor, job.ticket_id)
    if ticket.version != job.ticket_version and job.review_decision is None:
        raise ApiError(409, "stale_suggestion", "The ticket changed; analyze again")
    suggestion = validated_suggestion(session, actor, job)
    return {"job_id": str(job.id), "ticket_version": job.ticket_version, "review_decision": job.review_decision,
            "suggestion": suggestion.model_dump(mode="json")}


def review(session, actor_id, job_id, payload, key):
    actor = _actor(session, actor_id)
    if actor.role not in {"agent", "manager"}:
        raise ApiError(403, "forbidden", "Your current role cannot use this feature")
    job = session.get(AnalysisJob, job_id)
    if job is None:
        raise ApiError(404, "not_found", "The suggestion does not exist or is not accessible")
    job = session.scalar(select(AnalysisJob).where(AnalysisJob.id == job_id).with_for_update().execution_options(populate_existing=True))
    ticket = visible_ticket(session, actor, job.ticket_id, lock=True)
    suggestion = validated_suggestion(session, actor, job)
    record, replay = claim(session, actor.id, job.id, "suggestion_review", key, payload)
    if replay:
        return replay
    _version(ticket, payload.expected_version)
    if job.review_decision is not None:
        raise ApiError(409, "already_reviewed", "This suggestion has already been reviewed")
    if ticket.version != job.ticket_version or ticket.archived or ticket.status == "closed":
        raise ApiError(409, "stale_suggestion", "The ticket changed; analyze again")
    if not suggestion.citations and payload.decision != "rejected":
        raise ApiError(409, "evidence_required", "Review this ticket manually before replying")
    message = None
    if payload.decision != "rejected":
        from supportops.schemas import MessageCreate
        try:
            checked = MessageCreate(expected_version=ticket.version, visibility="public", body=payload.edited_body if payload.decision == "edited" else suggestion.reply_draft)
        except ValidationError:
            raise ApiError(422, "invalid_draft", "The draft cannot be sent; edit it before continuing") from None
        message = TicketMessage(id=uuid4(), ticket_id=ticket.id, author_id=actor.id, visibility="public", body=checked.body)
        session.add(message)
        session.flush()
    ticket = _update(session, ticket, payload.expected_version)
    _event(session, ticket, actor, "message_added" if message else "updated", {"message_id": str(message.id) if message else None, "visibility": "public" if message else None})
    job.review_decision = payload.decision
    job.reviewer_id = actor.id
    job.review_message_id = message.id if message else None
    job.reviewed_at = datetime.now(timezone.utc)
    return finish(session, record, 200, ReviewReceipt(job_id=job.id, decision=payload.decision,
        message_id=message.id if message else None, ticket_version=ticket.version))
