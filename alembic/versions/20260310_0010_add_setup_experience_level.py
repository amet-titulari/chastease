"""add setup_experience_level to auth_users

Revision ID: 20260310_0010
Revises: 20260310_0009
Create Date: 2026-03-10 00:10:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260310_0010"
down_revision = "20260310_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "auth_users",
        sa.Column("setup_experience_level", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("auth_users", "setup_experience_level")
