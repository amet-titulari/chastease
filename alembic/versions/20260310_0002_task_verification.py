"""task verification fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # tasks.requires_verification and tasks.verification_criteria already exist
    # verifications.linked_task_id already exists
    # Only add the missing column:
    op.add_column("verifications", sa.Column("verification_criteria", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("verifications", "verification_criteria")
    op.drop_column("verifications", "linked_task_id")
    op.drop_column("tasks", "verification_criteria")
    op.drop_column("tasks", "requires_verification")
