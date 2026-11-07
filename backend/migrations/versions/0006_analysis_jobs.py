"""Persist analysis jobs and lease state."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006_analysis_jobs"
down_revision = "0005_knowledge_retrieval"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "analysis_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("requester_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("ticket_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_token", sa.Uuid()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("error_code", sa.String(32)),
        sa.Column("result", JSONB(none_as_null=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('queued','running','succeeded','failed')", name="ck_job_status"),
        sa.CheckConstraint("attempts BETWEEN 0 AND 3 AND ticket_version > 0", name="ck_job_attempts"),
        sa.CheckConstraint("(status = 'running' AND lease_token IS NOT NULL AND lease_expires_at IS NOT NULL) OR (status <> 'running' AND lease_token IS NULL AND lease_expires_at IS NULL)", name="ck_job_lease"),
    )
    op.create_index("ix_jobs_claim", "analysis_jobs", ["status", "next_attempt_at", "created_at"])


def downgrade():
    op.drop_index("ix_jobs_claim", table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
