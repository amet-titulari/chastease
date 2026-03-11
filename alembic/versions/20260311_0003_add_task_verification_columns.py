"""add missing task verification columns

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("requires_verification", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("tasks", sa.Column("verification_criteria", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "verification_criteria")
    op.drop_column("tasks", "requires_verification")
