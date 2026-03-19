"""expand auth user password hash length

Revision ID: 0028
Revises: 0027
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def _table_exists(inspector, table_name: str) -> bool:
    return inspector.has_table(table_name)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "auth_users"):
        return

    with op.batch_alter_table("auth_users") as batch_op:
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(length=64),
            type_=sa.String(length=255),
            existing_nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "auth_users"):
        return

    with op.batch_alter_table("auth_users") as batch_op:
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(length=255),
            type_=sa.String(length=64),
            existing_nullable=False,
        )