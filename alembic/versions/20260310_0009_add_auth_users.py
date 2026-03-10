"""add auth users table

Revision ID: 20260310_0009
Revises: 20260310_0008
Create Date: 2026-03-10 00:09:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260310_0009"
down_revision = "20260310_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=64), nullable=False),
        sa.Column("password_salt", sa.String(length=32), nullable=False),
        sa.Column("session_token", sa.String(length=128), nullable=True),
        sa.Column("setup_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("setup_style", sa.String(length=80), nullable=True),
        sa.Column("setup_goal", sa.String(length=120), nullable=True),
        sa.Column("setup_boundary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_auth_users_id", "auth_users", ["id"], unique=False)
    op.create_index("ix_auth_users_username", "auth_users", ["username"], unique=True)
    op.create_index("ix_auth_users_email", "auth_users", ["email"], unique=True)
    op.create_index("ix_auth_users_session_token", "auth_users", ["session_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_auth_users_session_token", table_name="auth_users")
    op.drop_index("ix_auth_users_email", table_name="auth_users")
    op.drop_index("ix_auth_users_username", table_name="auth_users")
    op.drop_index("ix_auth_users_id", table_name="auth_users")
    op.drop_table("auth_users")
