"""add prompt metadata columns to messages

Revision ID: 0027
Revises: 0026
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0027"
down_revision = "0026"
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
    if not _table_exists(inspector, "messages"):
        return

    with op.batch_alter_table("messages") as batch_op:
        if not _column_exists(inspector, "messages", "prompt_version"):
            batch_op.add_column(sa.Column("prompt_version", sa.String(length=40), nullable=True))
        if not _column_exists(inspector, "messages", "prompt_templates_json"):
            batch_op.add_column(sa.Column("prompt_templates_json", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "messages"):
        return

    with op.batch_alter_table("messages") as batch_op:
        if _column_exists(inspector, "messages", "prompt_templates_json"):
            batch_op.drop_column("prompt_templates_json")
        if _column_exists(inspector, "messages", "prompt_version"):
            batch_op.drop_column("prompt_version")