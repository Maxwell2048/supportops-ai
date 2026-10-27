"""Immutable knowledge snapshots and transactional publication audit.

Keep historical ticket audit constraints intact; knowledge has its own FK-backed audit stream.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_knowledge_versions"
down_revision = "0003_audit_events"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "knowledge_articles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("latest_version_number", sa.Integer(), server_default="1", nullable=False),
        sa.Column("published_version_id", sa.Uuid(), nullable=True),
        sa.Column("archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("revision > 0 AND latest_version_number > 0 AND revision >= latest_version_number", name="ck_knowledge_revision"),
        sa.CheckConstraint("NOT archived OR published_version_id IS NOT NULL", name="ck_knowledge_archive"),
    )
    op.create_table(
        "knowledge_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("article_id", sa.Uuid(), sa.ForeignKey("knowledge_articles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("source_kind", sa.String(16), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("license_note", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("article_id", "number", name="uq_knowledge_version_number"),
        sa.UniqueConstraint("article_id", "id", name="uq_knowledge_article_version"),
        sa.CheckConstraint("number > 0", name="ck_knowledge_number"),
        sa.CheckConstraint("scope IN ('support','management')", name="ck_knowledge_scope"),
        sa.CheckConstraint("length(trim(title)) BETWEEN 1 AND 200 AND length(trim(body)) BETWEEN 1 AND 50000", name="ck_knowledge_content"),
        sa.CheckConstraint("source_kind IN ('synthetic','licensed') AND length(trim(source_reference)) BETWEEN 1 AND 2000 AND length(trim(license_note)) BETWEEN 1 AND 1000", name="ck_knowledge_source"),
        sa.CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="ck_knowledge_hash"),
    )
    op.create_foreign_key("fk_knowledge_published_version", "knowledge_articles", "knowledge_versions", ["id", "published_version_id"], ["article_id", "id"], ondelete="RESTRICT")
    op.create_table(
        "knowledge_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("article_id", sa.Uuid(), sa.ForeignKey("knowledge_articles.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("article_revision", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_role", sa.String(20), server_default="manager", nullable=False),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("result", sa.String(16), server_default="success", nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("changes", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("article_id", "article_revision", name="uq_knowledge_event_revision"),
        sa.ForeignKeyConstraint(["article_id", "version_id"], ["knowledge_versions.article_id", "knowledge_versions.id"], name="fk_knowledge_event_version", ondelete="RESTRICT"),
        sa.CheckConstraint("article_revision > 0 AND actor_role = 'manager' AND result = 'success'", name="ck_knowledge_event_actor"),
        sa.CheckConstraint("action IN ('draft_created','published','archived')", name="ck_knowledge_event_action"),
    )
    op.create_index("ix_knowledge_events_version_action", "knowledge_events", ["version_id", "action"])
    op.create_index("ix_knowledge_events_request", "knowledge_events", ["request_id"])
    op.execute("""CREATE FUNCTION reject_knowledge_history_change() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Knowledge history is immutable' USING ERRCODE = '23514'; END; $$""")
    for table in ("knowledge_versions", "knowledge_events"):
        op.execute(f"CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE OR TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION reject_knowledge_history_change()")


def downgrade():
    op.drop_constraint("fk_knowledge_published_version", "knowledge_articles", type_="foreignkey")
    op.drop_table("knowledge_events")
    op.drop_table("knowledge_versions")
    op.drop_table("knowledge_articles")
    op.execute("DROP FUNCTION reject_knowledge_history_change()")
