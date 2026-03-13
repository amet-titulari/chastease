"""drop legacy auth user setup fields

Revision ID: 0012
Revises: 0011
Create Date: 2026-03-16
"""

from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


LEGACY_COLUMNS = [
    "setup_experience_level",
    "setup_style",
    "setup_goal",
    "setup_boundary",
    "setup_wearer_nickname",
    "setup_hard_limits",
    "setup_penalty_multiplier",
    "setup_gentle_mode",
]


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

    existing = [name for name in LEGACY_COLUMNS if _column_exists(inspector, "auth_users", name)]
    if not existing:
        return

    with op.batch_alter_table("auth_users") as batch_op:
        for name in existing:
            batch_op.drop_column(name)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _table_exists(inspector, "auth_users"):
        return

    with op.batch_alter_table("auth_users") as batch_op:
        if not _column_exists(inspector, "auth_users", "setup_experience_level"):
            batch_op.add_column(sa.Column("setup_experience_level", sa.String(length=50), nullable=True))
        if not _column_exists(inspector, "auth_users", "setup_style"):
            batch_op.add_column(sa.Column("setup_style", sa.String(length=80), nullable=True))
        if not _column_exists(inspector, "auth_users", "setup_goal"):
            batch_op.add_column(sa.Column("setup_goal", sa.String(length=120), nullable=True))
        if not _column_exists(inspector, "auth_users", "setup_boundary"):
            batch_op.add_column(sa.Column("setup_boundary", sa.Text(), nullable=True))
        if not _column_exists(inspector, "auth_users", "setup_wearer_nickname"):
            batch_op.add_column(sa.Column("setup_wearer_nickname", sa.String(length=80), nullable=True))
        if not _column_exists(inspector, "auth_users", "setup_hard_limits"):
            batch_op.add_column(sa.Column("setup_hard_limits", sa.Text(), nullable=True))
        if not _column_exists(inspector, "auth_users", "setup_penalty_multiplier"):
            batch_op.add_column(sa.Column("setup_penalty_multiplier", sa.Float(), nullable=True))
        if not _column_exists(inspector, "auth_users", "setup_gentle_mode"):
            batch_op.add_column(sa.Column("setup_gentle_mode", sa.Boolean(), nullable=False, server_default=sa.text("0")))
