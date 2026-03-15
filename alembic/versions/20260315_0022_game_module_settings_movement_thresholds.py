"""add movement thresholds to game module settings

Revision ID: 0022
Revises: 0021
Create Date: 2026-03-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0022"
down_revision = "0021"
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

    with op.batch_alter_table(table_name) as batch_op:
        if not _column_exists(inspector, table_name, "movement_easy_pose_deviation"):
            batch_op.add_column(sa.Column("movement_easy_pose_deviation", sa.Float(), nullable=True))
        if not _column_exists(inspector, table_name, "movement_easy_stillness"):
            batch_op.add_column(sa.Column("movement_easy_stillness", sa.Float(), nullable=True))
        if not _column_exists(inspector, table_name, "movement_medium_pose_deviation"):
            batch_op.add_column(sa.Column("movement_medium_pose_deviation", sa.Float(), nullable=True))
        if not _column_exists(inspector, table_name, "movement_medium_stillness"):
            batch_op.add_column(sa.Column("movement_medium_stillness", sa.Float(), nullable=True))
        if not _column_exists(inspector, table_name, "movement_hard_pose_deviation"):
            batch_op.add_column(sa.Column("movement_hard_pose_deviation", sa.Float(), nullable=True))
        if not _column_exists(inspector, table_name, "movement_hard_stillness"):
            batch_op.add_column(sa.Column("movement_hard_stillness", sa.Float(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "game_module_settings"

    if not inspector.has_table(table_name):
        return

    with op.batch_alter_table(table_name) as batch_op:
        if _column_exists(inspector, table_name, "movement_hard_stillness"):
            batch_op.drop_column("movement_hard_stillness")
        if _column_exists(inspector, table_name, "movement_hard_pose_deviation"):
            batch_op.drop_column("movement_hard_pose_deviation")
        if _column_exists(inspector, table_name, "movement_medium_stillness"):
            batch_op.drop_column("movement_medium_stillness")
        if _column_exists(inspector, table_name, "movement_medium_pose_deviation"):
            batch_op.drop_column("movement_medium_pose_deviation")
        if _column_exists(inspector, table_name, "movement_easy_stillness"):
            batch_op.drop_column("movement_easy_stillness")
        if _column_exists(inspector, table_name, "movement_easy_pose_deviation"):
            batch_op.drop_column("movement_easy_pose_deviation")
