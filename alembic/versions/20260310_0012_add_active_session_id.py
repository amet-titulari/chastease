"""add active_session_id to auth_users

Revision ID: 20260310_0012
Revises: 20260310_0011
Create Date: 2026-03-10 00:12:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260310_0012"
down_revision = "20260310_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "auth_users",
        sa.Column("active_session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("auth_users", "active_session_id")
