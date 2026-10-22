"""Successful ticket audit records commit with the business write."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_audit_events"
down_revision = "0002_ticket_idempotency"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_role", sa.String(20), nullable=False),
        sa.Column("resource_type", sa.String(24), server_default="ticket", nullable=False),
        sa.Column("resource_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("action", sa.String(48), nullable=False),
        sa.Column("result", sa.String(16), server_default="success", nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("ticket_version", sa.Integer(), nullable=False),
        sa.Column("changes", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("actor_role IN ('requester','agent','manager')", name="ck_audit_role"),
        sa.CheckConstraint("resource_type = 'ticket' AND result = 'success'", name="ck_audit_resource_result"),
        sa.CheckConstraint("action IN ('ticket.created','ticket.assigned','ticket.updated','ticket.message_added')", name="ck_audit_action"),
        sa.CheckConstraint("ticket_version > 0", name="ck_audit_version"),
        sa.UniqueConstraint("resource_id", "ticket_version", name="uq_audit_ticket_version"),
    )
    op.create_index("ix_audit_created", "audit_events", ["created_at", "id"])
    op.create_index("ix_audit_resource_created", "audit_events", ["resource_id", "created_at", "id"])
    op.create_index("ix_audit_request", "audit_events", ["request_id"])


def downgrade():
    op.drop_table("audit_events")
