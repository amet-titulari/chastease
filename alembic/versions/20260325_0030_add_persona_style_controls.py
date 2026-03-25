"""add persona style controls

Revision ID: 0030
Revises: 0029
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa


revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def _column_names(inspector, table_name: str) -> set[str]:
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "personas"):
        return

    columns = _column_names(inspector, "personas")
    with op.batch_alter_table("personas") as batch_op:
        if "formatting_style" not in columns:
            batch_op.add_column(sa.Column("formatting_style", sa.String(length=30), nullable=True))
        if "verbosity_style" not in columns:
            batch_op.add_column(sa.Column("verbosity_style", sa.String(length=30), nullable=True))
        if "praise_style" not in columns:
            batch_op.add_column(sa.Column("praise_style", sa.String(length=30), nullable=True))
        if "repetition_guard" not in columns:
            batch_op.add_column(sa.Column("repetition_guard", sa.String(length=30), nullable=True))
        if "context_exposition_style" not in columns:
            batch_op.add_column(sa.Column("context_exposition_style", sa.String(length=30), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "personas"):
        return

    columns = _column_names(inspector, "personas")
    with op.batch_alter_table("personas") as batch_op:
        if "context_exposition_style" in columns:
            batch_op.drop_column("context_exposition_style")
        if "repetition_guard" in columns:
            batch_op.drop_column("repetition_guard")
        if "praise_style" in columns:
            batch_op.drop_column("praise_style")
        if "verbosity_style" in columns:
            batch_op.drop_column("verbosity_style")
        if "formatting_style" in columns:
            batch_op.drop_column("formatting_style")
