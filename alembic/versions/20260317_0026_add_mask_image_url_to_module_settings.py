"""add mask_image_url to game_module_settings

Revision ID: 0026
Revises: 0025
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    if not inspector.has_table(table_name):
        return False
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _column_exists(inspector, "game_module_settings", "mask_image_url"):
        op.add_column("game_module_settings", sa.Column("mask_image_url", sa.String(512), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _column_exists(inspector, "game_module_settings", "mask_image_url"):
        op.drop_column("game_module_settings", "mask_image_url")
