"""Audit every MCP tool call: tool, actor, outcome and object IDs, never free-text arguments."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0011_mcp_tool_calls"
down_revision = "0010_job_tool_trace"
branch_labels = None
depends_on = None

TOOLS = "'list_my_tickets','get_ticket','ticket_history','search_knowledge','unknown'"
OUTCOMES = "'ok','invalid_session','forbidden','unknown_tool','invalid_arguments','not_found'"


def upgrade():
    op.create_table(
        "mcp_tool_calls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        # Nullable: a correctly signed token whose subject has no user row is still recorded.
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")),
        sa.Column("actor_role", sa.String(20)),
        sa.Column("tool", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        # The requested ticket ID, kept even when it does not exist, so probing is visible. No foreign key.
        sa.Column("ticket_id", sa.Uuid()),
        sa.Column("result_ids", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("result_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("actor_role IS NULL OR actor_role IN ('requester','agent','manager')", name="ck_mcp_role"),
        sa.CheckConstraint(f"tool IN ({TOOLS})", name="ck_mcp_tool"),
        sa.CheckConstraint(f"outcome IN ({OUTCOMES})", name="ck_mcp_outcome"),
        sa.CheckConstraint("jsonb_typeof(result_ids) = 'array' AND jsonb_array_length(result_ids) <= 20 AND result_count >= 0", name="ck_mcp_results"),
    )
    op.create_index("ix_mcp_calls_created", "mcp_tool_calls", ["created_at", "id"])
    op.create_index("ix_mcp_calls_actor_created", "mcp_tool_calls", ["actor_id", "created_at", "id"])


def downgrade():
    op.drop_table("mcp_tool_calls")
