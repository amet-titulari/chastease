"""add reference landmarks to game posture templates

Revision ID: 0024
Revises: 0023
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa


revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    if not inspector.has_table(table_name):
        return False
    return any(col.get("name") == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "game_posture_templates"

    if not inspector.has_table(table_name):
        return

    with op.batch_alter_table(table_name) as batch_op:
        if not _column_exists(inspector, table_name, "reference_landmarks_json"):
            batch_op.add_column(sa.Column("reference_landmarks_json", sa.Text(), nullable=True))
        if not _column_exists(inspector, table_name, "reference_landmarks_detected_at"):
            batch_op.add_column(sa.Column("reference_landmarks_detected_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "game_posture_templates"

    if not inspector.has_table(table_name):
        return

    with op.batch_alter_table(table_name) as batch_op:
        if _column_exists(inspector, table_name, "reference_landmarks_detected_at"):
            batch_op.drop_column("reference_landmarks_detected_at")
        if _column_exists(inspector, table_name, "reference_landmarks_json"):
            batch_op.drop_column("reference_landmarks_json")
