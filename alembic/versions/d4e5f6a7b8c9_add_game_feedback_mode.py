"""add game feedback mode

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-24 12:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("game_module_settings", sa.Column("game_feedback_mode", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("game_module_settings", "game_feedback_mode")
