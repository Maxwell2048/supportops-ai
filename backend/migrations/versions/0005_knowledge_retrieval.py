"""Versioned immutable retrieval materializations and real pgvector storage."""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0005_knowledge_retrieval"
down_revision = "0004_knowledge_versions"
branch_labels = None
depends_on = None


def upgrade():
    # The extension is database-scoped; serialize concurrent isolated-schema upgrades.
    op.execute("SELECT pg_advisory_xact_lock(5341431405)")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")
    op.create_table("knowledge_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("knowledge_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("chunker", sa.String(48), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint("version_id", "chunker", "ordinal", name="uq_chunk_ordinal"),
        sa.CheckConstraint("ordinal >= 0 AND start_offset >= 0 AND end_offset > start_offset AND end_offset - start_offset = length(content)", name="ck_chunk_offsets"),
        sa.CheckConstraint("content_hash ~ '^[0-9a-f]{64}$' AND length(content) BETWEEN 1 AND 400", name="ck_chunk_content"))
    op.create_table("embedding_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("model_digest", sa.String(64), nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("normalization", sa.String(24), nullable=False),
        sa.Column("license_note", sa.Text(), nullable=False),
        sa.UniqueConstraint("id", "dimensions", name="uq_profile_dimension"),
        sa.CheckConstraint("dimensions BETWEEN 1 AND 4096 AND provider IN ('ollama','mock')", name="ck_profile_dimensions"),
        sa.CheckConstraint("model_digest ~ '^[0-9a-f]{64}$' AND normalization = 'l2-v1'", name="ck_profile_spec"))
    op.create_table("knowledge_embeddings",
        sa.Column("chunk_id", sa.Uuid(), sa.ForeignKey("knowledge_chunks.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("profile_id", sa.Uuid(), primary_key=True),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        sa.ForeignKeyConstraint(["profile_id", "dimensions"], ["embedding_profiles.id", "embedding_profiles.dimensions"], name="fk_embedding_profile_dimension", ondelete="RESTRICT"),
        sa.CheckConstraint("vector_dims(embedding) = dimensions AND abs(vector_norm(embedding) - 1) < 0.0001", name="ck_embedding_vector"))
    op.create_table("knowledge_indexes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("knowledge_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("representation", sa.String(64), nullable=False),
        sa.Column("chunker", sa.String(48), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("profile_id", sa.Uuid(), sa.ForeignKey("embedding_profiles.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("version_id", "representation", name="uq_knowledge_representation"),
        sa.CheckConstraint("chunk_count > 0 AND representation ~ '^[0-9a-f]{64}$'", name="ck_index_representation"),
        sa.CheckConstraint("(mode = 'keyword' AND profile_id IS NULL) OR (mode = 'vector' AND profile_id IS NOT NULL)", name="ck_index_mode"))
    for table in ("knowledge_chunks", "embedding_profiles", "knowledge_embeddings", "knowledge_indexes"):
        op.execute(f"CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE OR TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION reject_knowledge_history_change()")


def downgrade():
    for table in ("knowledge_indexes", "knowledge_embeddings", "embedding_profiles", "knowledge_chunks"):
        op.drop_table(table)
    # Do not remove the shared database extension used by other schemas.
