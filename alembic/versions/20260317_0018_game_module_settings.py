"""add game module settings table

Revision ID: 0018
Revises: 0017
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_module_settings",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("module_key", sa.String(length=120), nullable=False, unique=True),
        sa.Column("easy_target_multiplier", sa.Float(), nullable=False, server_default=sa.text("0.85")),
        sa.Column("hard_target_multiplier", sa.Float(), nullable=False, server_default=sa.text("1.25")),
        sa.Column("target_randomization_percent", sa.Integer(), nullable=False, server_default=sa.text("10")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_game_module_settings_module_key", "game_module_settings", ["module_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_game_module_settings_module_key", table_name="game_module_settings")
    op.drop_table("game_module_settings")
