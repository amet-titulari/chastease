"""drop scenarios character_ref column

Revision ID: 0014
Revises: 0013
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
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
    if not _table_exists(inspector, "scenarios"):
        return
    if _column_exists(inspector, "scenarios", "character_ref"):
        with op.batch_alter_table("scenarios") as batch_op:
            batch_op.drop_column("character_ref")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "scenarios"):
        return
    if not _column_exists(inspector, "scenarios", "character_ref"):
        with op.batch_alter_table("scenarios") as batch_op:
            batch_op.add_column(sa.Column("character_ref", sa.String(length=120), nullable=True))
