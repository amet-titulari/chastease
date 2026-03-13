"""add per-session hygiene opening max duration

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("hygiene_opening_max_duration_seconds", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("sessions", "hygiene_opening_max_duration_seconds")
