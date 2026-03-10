"""add active_session_id to auth_users

Revision ID: 20260310_0012
Revises: 20260310_0011
Create Date: 2026-03-10 00:12:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260310_0012"
down_revision = "20260310_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = [row[1] for row in bind.execute(sa.text("PRAGMA table_info(auth_users)")).fetchall()]
    if "active_session_id" not in cols:
        # SQLite does not support adding FK constraints via ALTER TABLE;
        # add as a plain integer column (FK is enforced at the ORM level).
        op.add_column(
            "auth_users",
            sa.Column("active_session_id", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("auth_users", "active_session_id")
