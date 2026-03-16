"""add pose similarity thresholds to game module settings

Revision ID: 0025
Revises: 0024
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa


revision = "0025"
down_revision = "0024"
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
        if not _column_exists(inspector, table_name, "pose_similarity_min_score_easy"):
            batch_op.add_column(sa.Column("pose_similarity_min_score_easy", sa.Float(), nullable=True))
        if not _column_exists(inspector, table_name, "pose_similarity_min_score_medium"):
            batch_op.add_column(sa.Column("pose_similarity_min_score_medium", sa.Float(), nullable=True))
        if not _column_exists(inspector, table_name, "pose_similarity_min_score_hard"):
            batch_op.add_column(sa.Column("pose_similarity_min_score_hard", sa.Float(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "game_module_settings"

    if not inspector.has_table(table_name):
        return

    with op.batch_alter_table(table_name) as batch_op:
        if _column_exists(inspector, table_name, "pose_similarity_min_score_hard"):
            batch_op.drop_column("pose_similarity_min_score_hard")
        if _column_exists(inspector, table_name, "pose_similarity_min_score_medium"):
            batch_op.drop_column("pose_similarity_min_score_medium")
        if _column_exists(inspector, table_name, "pose_similarity_min_score_easy"):
            batch_op.drop_column("pose_similarity_min_score_easy")
