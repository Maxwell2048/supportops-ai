"""Initial user/ticket/message/event schema. Keep historical migrations immutable."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_ticket_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('requester','agent','manager')", name="ck_users_role"),
        sa.CheckConstraint("email = lower(email) AND length(trim(email)) > 0", name="ck_users_email"),
    )
    op.create_table(
        "tickets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("requester_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assignee_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(12), nullable=False, server_default="normal"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('open','in_progress','waiting_customer','resolved','closed')", name="ck_tickets_status"),
        sa.CheckConstraint("priority IN ('low','normal','high','urgent')", name="ck_tickets_priority"),
        sa.CheckConstraint("version > 0", name="ck_tickets_version"),
        sa.CheckConstraint("length(trim(title)) > 0", name="ck_tickets_title"),
        sa.CheckConstraint("length(trim(body)) BETWEEN 1 AND 10000", name="ck_tickets_body"),
        sa.CheckConstraint("NOT archived OR status = 'closed'", name="ck_tickets_archive"),
        sa.CheckConstraint("status NOT IN ('in_progress','waiting_customer') OR assignee_id IS NOT NULL", name="ck_tickets_assignee"),
    )
    op.create_index("ix_tickets_requester_created", "tickets", ["requester_id", "created_at", "id"])
    op.create_index("ix_tickets_assignee_status", "tickets", ["assignee_id", "status", "created_at", "id"])
    op.create_table(
        "ticket_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("author_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("visibility", sa.String(12), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("visibility IN ('public','internal')", name="ck_messages_visibility"),
        sa.CheckConstraint("length(trim(body)) BETWEEN 1 AND 10000", name="ck_messages_body"),
    )
    op.create_index("ix_messages_ticket_created", "ticket_messages", ["ticket_id", "created_at", "id"])
    op.create_table(
        "ticket_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("tickets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("changes", postgresql.JSONB(), nullable=False),
        sa.Column("ticket_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("ticket_version > 0", name="ck_events_version"),
        sa.UniqueConstraint("ticket_id", "ticket_version", name="uq_events_ticket_version"),
    )


def downgrade():
    op.drop_table("ticket_events")
    op.drop_table("ticket_messages")
    op.drop_table("tickets")
    op.drop_table("users")
