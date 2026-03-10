"""add task consequence tracking

Revision ID: 20260310_0005
Revises: 20260310_0004
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260310_0005"
down_revision = "20260310_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("consequence_applied_seconds", sa.Integer(), nullable=True))
    op.add_column("tasks", sa.Column("consequence_applied_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "consequence_applied_at")
    op.drop_column("tasks", "consequence_applied_seconds")
