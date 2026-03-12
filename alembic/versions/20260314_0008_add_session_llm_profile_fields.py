"""add per-session llm profile fields

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-14
"""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sessions", sa.Column("llm_provider", sa.String(length=50), nullable=True))
    op.add_column("sessions", sa.Column("llm_api_url", sa.String(length=500), nullable=True))
    op.add_column("sessions", sa.Column("llm_api_key", sa.Text(), nullable=True))
    op.add_column("sessions", sa.Column("llm_chat_model", sa.String(length=120), nullable=True))
    op.add_column("sessions", sa.Column("llm_vision_model", sa.String(length=120), nullable=True))
    op.add_column(
        "sessions",
        sa.Column("llm_profile_active", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("sessions", "llm_profile_active")
    op.drop_column("sessions", "llm_vision_model")
    op.drop_column("sessions", "llm_chat_model")
    op.drop_column("sessions", "llm_api_key")
    op.drop_column("sessions", "llm_api_url")
    op.drop_column("sessions", "llm_provider")
