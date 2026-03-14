"""add transition_seconds to game_runs

Revision ID: 0019
Revises: 0018
Create Date: 2026-03-18
"""

from alembic import op
import sqlalchemy as sa


revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    if not _table_exists(inspector, table_name):
        return False
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "game_runs"):
        return
    if _column_exists(inspector, "game_runs", "transition_seconds"):
        return

    with op.batch_alter_table("game_runs") as batch_op:
        batch_op.add_column(sa.Column("transition_seconds", sa.Integer(), nullable=False, server_default=sa.text("8")))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "game_runs"):
        return
    if not _column_exists(inspector, "game_runs", "transition_seconds"):
        return

    with op.batch_alter_table("game_runs") as batch_op:
        batch_op.drop_column("transition_seconds")
