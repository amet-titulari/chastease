"""add websocket auth token to sessions

Revision ID: 20260310_0006
Revises: 20260310_0005
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260310_0006"
down_revision = "20260310_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("ws_auth_token", sa.String(length=80), nullable=True))
    op.add_column("sessions", sa.Column("ws_auth_token_created_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_sessions_ws_auth_token", "sessions", ["ws_auth_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_sessions_ws_auth_token", table_name="sessions")
    op.drop_column("sessions", "ws_auth_token_created_at")
    op.drop_column("sessions", "ws_auth_token")
