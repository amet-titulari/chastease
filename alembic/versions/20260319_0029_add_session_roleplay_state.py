"""add session roleplay state

Revision ID: 0029
Revises: 0028
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _column_names(inspector, table_name: str) -> set[str]:
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "sessions"):
        return

    columns = _column_names(inspector, "sessions")
    with op.batch_alter_table("sessions") as batch_op:
        if "relationship_state_json" not in columns:
            batch_op.add_column(sa.Column("relationship_state_json", sa.Text(), nullable=True))
        if "protocol_state_json" not in columns:
            batch_op.add_column(sa.Column("protocol_state_json", sa.Text(), nullable=True))
        if "scene_state_json" not in columns:
            batch_op.add_column(sa.Column("scene_state_json", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "sessions"):
        return

    columns = _column_names(inspector, "sessions")
    with op.batch_alter_table("sessions") as batch_op:
        if "scene_state_json" in columns:
            batch_op.drop_column("scene_state_json")
        if "protocol_state_json" in columns:
            batch_op.drop_column("protocol_state_json")
        if "relationship_state_json" in columns:
            batch_op.drop_column("relationship_state_json")
