"""add behavior profiles to persona and scenario

Revision ID: 0031
Revises: 0030
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa


revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _column_names(inspector, table_name: str) -> set[str]:
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "personas"):
        columns = _column_names(inspector, "personas")
        with op.batch_alter_table("personas") as batch_op:
            if "behavior_profile_json" not in columns:
                batch_op.add_column(sa.Column("behavior_profile_json", sa.Text(), nullable=True))

    if _table_exists(inspector, "scenarios"):
        columns = _column_names(inspector, "scenarios")
        with op.batch_alter_table("scenarios") as batch_op:
            if "behavior_profile_json" not in columns:
                batch_op.add_column(sa.Column("behavior_profile_json", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, "scenarios"):
        columns = _column_names(inspector, "scenarios")
        with op.batch_alter_table("scenarios") as batch_op:
            if "behavior_profile_json" in columns:
                batch_op.drop_column("behavior_profile_json")

    if _table_exists(inspector, "personas"):
        columns = _column_names(inspector, "personas")
        with op.batch_alter_table("personas") as batch_op:
            if "behavior_profile_json" in columns:
                batch_op.drop_column("behavior_profile_json")
