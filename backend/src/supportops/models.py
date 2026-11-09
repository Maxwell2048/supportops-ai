"""Persistent business schema; application services enforce current role/object authorization."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('requester','agent','manager')", name="ck_users_role"),
        CheckConstraint("email = lower(email) AND length(trim(email)) > 0", name="ck_users_email"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("status IN ('open','in_progress','waiting_customer','resolved','closed')", name="ck_tickets_status"),
        CheckConstraint("priority IN ('low','normal','high','urgent')", name="ck_tickets_priority"),
        CheckConstraint("version > 0", name="ck_tickets_version"),
        CheckConstraint("length(trim(title)) > 0", name="ck_tickets_title"),
        CheckConstraint("length(trim(body)) BETWEEN 1 AND 10000", name="ck_tickets_body"),
        CheckConstraint("contact_phone IS NULL OR (contact_phone = trim(contact_phone) AND contact_phone ~ '^[0-9+(). -]{3,40}$' AND contact_phone ~ '[0-9]')", name="ck_tickets_contact_phone"),
        CheckConstraint("NOT archived OR status = 'closed'", name="ck_tickets_archive"),
        CheckConstraint("status NOT IN ('in_progress','waiting_customer') OR assignee_id IS NOT NULL", name="ck_tickets_assignee"),
        Index("ix_tickets_requester_created", "requester_id", "created_at", "id"),
        Index("ix_tickets_assignee_status", "assignee_id", "status", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    requester_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assignee_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    contact_phone: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), server_default="open")
    priority: Mapped[str] = mapped_column(String(12), server_default="normal")
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    archived: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TicketMessage(Base):
    __tablename__ = "ticket_messages"
    __table_args__ = (
        CheckConstraint("visibility IN ('public','internal')", name="ck_messages_visibility"),
        CheckConstraint("length(trim(body)) BETWEEN 1 AND 10000", name="ck_messages_body"),
        Index("ix_messages_ticket_created", "ticket_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("tickets.id", ondelete="RESTRICT"))
    author_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    visibility: Mapped[str] = mapped_column(String(12))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TicketEvent(Base):
    __tablename__ = "ticket_events"
    __table_args__ = (
        CheckConstraint("ticket_version > 0", name="ck_events_version"),
        UniqueConstraint("ticket_id", "ticket_version", name="uq_events_ticket_version"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("tickets.id", ondelete="RESTRICT"))
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    event_type: Mapped[str] = mapped_column(String(40))
    changes: Mapped[dict] = mapped_column(JSONB)
    ticket_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("actor_id", "resource_id", "operation", "key", name="uq_idempotency_scope"),
        CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="ck_idempotency_hash"),
        CheckConstraint("length(key) BETWEEN 1 AND 128", name="ck_idempotency_key"),
        CheckConstraint("(response_status IS NULL AND response_body IS NULL) OR (response_status IS NOT NULL AND response_status BETWEEN 200 AND 299 AND response_body IS NOT NULL)", name="ck_idempotency_response"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    resource_id: Mapped[UUID] = mapped_column()
    operation: Mapped[str] = mapped_column(String(48))
    key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        CheckConstraint("actor_role IN ('requester','agent','manager')", name="ck_audit_role"),
        CheckConstraint("resource_type = 'ticket' AND result = 'success'", name="ck_audit_resource_result"),
        CheckConstraint("action IN ('ticket.created','ticket.assigned','ticket.updated','ticket.message_added')", name="ck_audit_action"),
        CheckConstraint("ticket_version > 0", name="ck_audit_version"),
        UniqueConstraint("resource_id", "ticket_version", name="uq_audit_ticket_version"),
        Index("ix_audit_created", "created_at", "id"),
        Index("ix_audit_resource_created", "resource_id", "created_at", "id"),
        Index("ix_audit_request", "request_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    actor_role: Mapped[str] = mapped_column(String(20))
    resource_type: Mapped[str] = mapped_column(String(24), server_default="ticket")
    resource_id: Mapped[UUID] = mapped_column(ForeignKey("tickets.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(48))
    result: Mapped[str] = mapped_column(String(16), server_default="success")
    request_id: Mapped[UUID] = mapped_column()
    ticket_version: Mapped[int] = mapped_column(Integer)
    changes: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"
    __table_args__ = (
        CheckConstraint("revision > 0 AND latest_version_number > 0 AND revision >= latest_version_number", name="ck_knowledge_revision"),
        CheckConstraint("NOT archived OR published_version_id IS NOT NULL", name="ck_knowledge_archive"),
        ForeignKeyConstraint(["id", "published_version_id"], ["knowledge_versions.article_id", "knowledge_versions.id"], name="fk_knowledge_published_version", use_alter=True, ondelete="RESTRICT"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    revision: Mapped[int] = mapped_column(Integer, server_default="1")
    latest_version_number: Mapped[int] = mapped_column(Integer, server_default="1")
    published_version_id: Mapped[UUID | None] = mapped_column()
    archived: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeVersion(Base):
    __tablename__ = "knowledge_versions"
    __table_args__ = (
        UniqueConstraint("article_id", "number", name="uq_knowledge_version_number"),
        UniqueConstraint("article_id", "id", name="uq_knowledge_article_version"),
        CheckConstraint("number > 0", name="ck_knowledge_number"),
        CheckConstraint("scope IN ('support','management')", name="ck_knowledge_scope"),
        CheckConstraint("length(trim(title)) BETWEEN 1 AND 200 AND length(trim(body)) BETWEEN 1 AND 50000", name="ck_knowledge_content"),
        CheckConstraint("source_kind IN ('synthetic','licensed') AND length(trim(source_reference)) BETWEEN 1 AND 2000 AND length(trim(license_note)) BETWEEN 1 AND 1000", name="ck_knowledge_source"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="ck_knowledge_hash"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    article_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_articles.id", ondelete="RESTRICT"))
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(String(20))
    source_kind: Mapped[str] = mapped_column(String(16))
    source_reference: Mapped[str] = mapped_column(Text)
    license_note: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeEvent(Base):
    __tablename__ = "knowledge_events"
    __table_args__ = (
        UniqueConstraint("article_id", "article_revision", name="uq_knowledge_event_revision"),
        ForeignKeyConstraint(["article_id", "version_id"], ["knowledge_versions.article_id", "knowledge_versions.id"], name="fk_knowledge_event_version", ondelete="RESTRICT"),
        CheckConstraint("article_revision > 0 AND actor_role = 'manager' AND result = 'success'", name="ck_knowledge_event_actor"),
        CheckConstraint("action IN ('draft_created','published','archived')", name="ck_knowledge_event_action"),
        Index("ix_knowledge_events_version_action", "version_id", "action"),
        Index("ix_knowledge_events_request", "request_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    article_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_articles.id", ondelete="RESTRICT"))
    version_id: Mapped[UUID] = mapped_column()
    article_revision: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    actor_role: Mapped[str] = mapped_column(String(20), server_default="manager")
    action: Mapped[str] = mapped_column(String(24))
    result: Mapped[str] = mapped_column(String(16), server_default="success")
    request_id: Mapped[UUID] = mapped_column()
    changes: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("version_id", "chunker", "ordinal", name="uq_chunk_ordinal"),
        CheckConstraint("ordinal >= 0 AND start_offset >= 0 AND end_offset > start_offset AND end_offset - start_offset = length(content)", name="ck_chunk_offsets"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$' AND length(content) BETWEEN 1 AND 400", name="ck_chunk_content"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    version_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_versions.id", ondelete="RESTRICT"))
    chunker: Mapped[str] = mapped_column(String(48))
    ordinal: Mapped[int] = mapped_column(Integer)
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))


class EmbeddingProfile(Base):
    __tablename__ = "embedding_profiles"
    __table_args__ = (
        UniqueConstraint("id", "dimensions", name="uq_profile_dimension"),
        CheckConstraint("dimensions BETWEEN 1 AND 4096 AND provider IN ('ollama','mock')", name="ck_profile_dimensions"),
        CheckConstraint("model_digest ~ '^[0-9a-f]{64}$' AND normalization = 'l2-v1'", name="ck_profile_spec"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(128))
    model_digest: Mapped[str] = mapped_column(String(64))
    dimensions: Mapped[int] = mapped_column(Integer)
    normalization: Mapped[str] = mapped_column(String(24))
    license_note: Mapped[str] = mapped_column(Text)


class KnowledgeEmbedding(Base):
    __tablename__ = "knowledge_embeddings"
    __table_args__ = (
        ForeignKeyConstraint(["profile_id", "dimensions"], ["embedding_profiles.id", "embedding_profiles.dimensions"], name="fk_embedding_profile_dimension", ondelete="RESTRICT"),
        CheckConstraint("vector_dims(embedding) = dimensions AND abs(vector_norm(embedding) - 1) < 0.0001", name="ck_embedding_vector"),
    )
    chunk_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_chunks.id", ondelete="RESTRICT"), primary_key=True)
    profile_id: Mapped[UUID] = mapped_column(primary_key=True)
    dimensions: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float]] = mapped_column(Vector())


class KnowledgeIndex(Base):
    __tablename__ = "knowledge_indexes"
    __table_args__ = (
        UniqueConstraint("version_id", "representation", name="uq_knowledge_representation"),
        CheckConstraint("chunk_count > 0 AND representation ~ '^[0-9a-f]{64}$'", name="ck_index_representation"),
        CheckConstraint("(mode = 'keyword' AND profile_id IS NULL) OR (mode = 'vector' AND profile_id IS NOT NULL)", name="ck_index_mode"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    version_id: Mapped[UUID] = mapped_column(ForeignKey("knowledge_versions.id", ondelete="RESTRICT"))
    representation: Mapped[str] = mapped_column(String(64))
    chunker: Mapped[str] = mapped_column(String(48))
    mode: Mapped[str] = mapped_column(String(16))
    profile_id: Mapped[UUID | None] = mapped_column(ForeignKey("embedding_profiles.id", ondelete="RESTRICT"))
    chunk_count: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    request_id: Mapped[UUID] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    __table_args__ = (
        CheckConstraint("status IN ('queued','running','succeeded','failed')", name="ck_job_status"),
        CheckConstraint("attempts BETWEEN 0 AND 3 AND ticket_version > 0", name="ck_job_attempts"),
        CheckConstraint("(status = 'running' AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL) OR (status <> 'running' AND lease_token IS NULL AND lease_expires_at IS NULL)", name="ck_job_lease"),
        Index("ix_jobs_claim", "status", "next_attempt_at", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("tickets.id", ondelete="RESTRICT"))
    requester_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    ticket_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    lease_token: Mapped[UUID | None] = mapped_column()
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    error_code: Mapped[str | None] = mapped_column(String(32))
    result: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    validation_version: Mapped[str | None] = mapped_column(String(16))
    generation_provider: Mapped[str | None] = mapped_column(String(16))
    generation_model: Mapped[str | None] = mapped_column(String(128))
    generation_digest: Mapped[str | None] = mapped_column(String(64))
    review_decision: Mapped[str | None] = mapped_column(String(16))
    reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    review_message_id: Mapped[UUID | None] = mapped_column(ForeignKey("ticket_messages.id", ondelete="RESTRICT"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
