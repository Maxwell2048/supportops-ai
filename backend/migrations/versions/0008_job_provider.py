"""Record generation provider provenance for analysis jobs."""
from alembic import op
import sqlalchemy as sa

revision = "0008_job_provider"
down_revision = "0007_job_review"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("analysis_jobs", sa.Column("generation_provider", sa.String(16)))
    op.add_column("analysis_jobs", sa.Column("generation_model", sa.String(128)))
    op.add_column("analysis_jobs", sa.Column("generation_digest", sa.String(64)))


def downgrade():
    for name in ("generation_digest", "generation_model", "generation_provider"):
        op.drop_column("analysis_jobs", name)
