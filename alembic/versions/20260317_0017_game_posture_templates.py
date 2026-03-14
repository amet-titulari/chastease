"""add game posture templates table

Revision ID: 0017
Revises: 0016
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_posture_templates",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("module_key", sa.String(length=120), nullable=False),
        sa.Column("posture_key", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("instruction", sa.Text(), nullable=True),
        sa.Column("target_seconds", sa.Integer(), nullable=False, server_default=sa.text("120")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_game_posture_templates_module_key", "game_posture_templates", ["module_key"])


def downgrade() -> None:
    op.drop_index("ix_game_posture_templates_module_key", table_name="game_posture_templates")
    op.drop_table("game_posture_templates")
