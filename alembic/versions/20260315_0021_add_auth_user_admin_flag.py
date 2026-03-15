"""add is_admin flag to auth_users

Revision ID: 0021
Revises: 0020
Create Date: 2026-03-15
"""

from alembic import op
import sqlalchemy as sa


revision = "0021"
down_revision = "0020"
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

    if not _table_exists(inspector, "auth_users"):
        return

    if not _column_exists(inspector, "auth_users", "is_admin"):
        with op.batch_alter_table("auth_users") as batch_op:
            batch_op.add_column(sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("0")))

    # Lockout protection for existing installs: ensure at least one admin exists.
    admin_count = bind.execute(sa.text("SELECT COUNT(1) FROM auth_users WHERE is_admin = 1")).scalar() or 0
    if int(admin_count) <= 0:
        first_id = bind.execute(sa.text("SELECT id FROM auth_users ORDER BY id ASC LIMIT 1")).scalar()
        if first_id is not None:
            bind.execute(sa.text("UPDATE auth_users SET is_admin = 1 WHERE id = :user_id"), {"user_id": int(first_id)})


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _table_exists(inspector, "auth_users"):
        return
    if not _column_exists(inspector, "auth_users", "is_admin"):
        return

    with op.batch_alter_table("auth_users") as batch_op:
        batch_op.drop_column("is_admin")
