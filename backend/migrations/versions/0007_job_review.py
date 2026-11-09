"""Store human decisions for validated analysis results."""
from alembic import op
import sqlalchemy as sa

revision = "0007_job_review"
down_revision = "0006_analysis_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("analysis_jobs", sa.Column("validation_version", sa.String(16)))
    op.add_column("analysis_jobs", sa.Column("review_decision", sa.String(16)))
    op.add_column("analysis_jobs", sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT")))
    op.add_column("analysis_jobs", sa.Column("review_message_id", sa.Uuid(), sa.ForeignKey("ticket_messages.id", ondelete="RESTRICT")))
    op.add_column("analysis_jobs", sa.Column("reviewed_at", sa.DateTime(timezone=True)))
    op.create_check_constraint("ck_job_review", "analysis_jobs", "(review_decision IS NULL AND reviewer_id IS NULL AND review_message_id IS NULL AND reviewed_at IS NULL) OR (review_decision IS NOT NULL AND review_decision IN ('accepted','edited') AND reviewer_id IS NOT NULL AND review_message_id IS NOT NULL AND reviewed_at IS NOT NULL) OR (review_decision IS NOT NULL AND review_decision = 'rejected' AND reviewer_id IS NOT NULL AND review_message_id IS NULL AND reviewed_at IS NOT NULL)")


def downgrade():
    op.drop_constraint("ck_job_review", "analysis_jobs", type_="check")
    for name in ("reviewed_at", "review_message_id", "reviewer_id", "review_decision", "validation_version"):
        op.drop_column("analysis_jobs", name)
