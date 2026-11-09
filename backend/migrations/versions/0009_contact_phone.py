"""Add an optional requester contact phone while preserving older tickets."""
from alembic import op
import sqlalchemy as sa

revision = "0009_contact_phone"
down_revision = "0008_job_provider"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("tickets", sa.Column("contact_phone", sa.String(40)))
    op.create_check_constraint("ck_tickets_contact_phone", "tickets", "contact_phone IS NULL OR (contact_phone = trim(contact_phone) AND contact_phone ~ '^[0-9+(). -]{3,40}$' AND contact_phone ~ '[0-9]')")


def downgrade():
    op.drop_constraint("ck_tickets_contact_phone", "tickets", type_="check")
    op.drop_column("tickets", "contact_phone")
