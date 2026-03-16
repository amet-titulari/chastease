"""add start_countdown_seconds to game module settings

Revision ID: 0023
Revises: 0022
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa


revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    if not inspector.has_table(table_name):
        return False
    return any(col.get("name") == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "game_module_settings"

    if not inspector.has_table(table_name):
        return
    if _column_exists(inspector, table_name, "start_countdown_seconds"):
        return

    with op.batch_alter_table(table_name) as batch_op:
        batch_op.add_column(
            sa.Column(
                "start_countdown_seconds",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("5"),
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "game_module_settings"

    if not inspector.has_table(table_name):
        return
    if not _column_exists(inspector, table_name, "start_countdown_seconds"):
        return

    with op.batch_alter_table(table_name) as batch_op:
        batch_op.drop_column("start_countdown_seconds")
