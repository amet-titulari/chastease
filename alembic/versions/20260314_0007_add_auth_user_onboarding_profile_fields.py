"""add onboarding profile fields to auth_users

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("auth_users", sa.Column("setup_wearer_nickname", sa.String(length=80), nullable=True))
    op.add_column("auth_users", sa.Column("setup_hard_limits", sa.Text(), nullable=True))
    op.add_column("auth_users", sa.Column("setup_penalty_multiplier", sa.Float(), nullable=True))
    op.add_column(
        "auth_users",
        sa.Column("setup_gentle_mode", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("auth_users", "setup_gentle_mode")
    op.drop_column("auth_users", "setup_penalty_multiplier")
    op.drop_column("auth_users", "setup_hard_limits")
    op.drop_column("auth_users", "setup_wearer_nickname")
