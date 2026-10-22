"""Persist successful idempotent write results in the business transaction."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_ticket_idempotency"
down_revision = "0001_ticket_foundation"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(48), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response_status", sa.Integer()),
        sa.Column("response_body", postgresql.JSONB(none_as_null=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("actor_id", "resource_id", "operation", "key", name="uq_idempotency_scope"),
        sa.CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="ck_idempotency_hash"),
        sa.CheckConstraint("length(key) BETWEEN 1 AND 128", name="ck_idempotency_key"),
        sa.CheckConstraint("(response_status IS NULL AND response_body IS NULL) OR (response_status IS NOT NULL AND response_status BETWEEN 200 AND 299 AND response_body IS NOT NULL)", name="ck_idempotency_response"),
    )


def downgrade():
    op.drop_table("idempotency_records")
