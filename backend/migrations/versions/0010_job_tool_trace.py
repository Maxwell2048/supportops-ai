"""Record the controlled read-only tool calls made during analysis."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0010_job_tool_trace"
down_revision = "0009_contact_phone"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("analysis_jobs", sa.Column("tool_trace", postgresql.JSONB(none_as_null=True)))


def downgrade():
    op.drop_column("analysis_jobs", "tool_trace")
