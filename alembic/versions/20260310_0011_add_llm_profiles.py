"""add llm_profiles table

Revision ID: 20260310_0011
Revises: 20260310_0010
Create Date: 2026-03-10 00:11:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260310_0011"
down_revision = "20260310_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_profiles",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("profile_key", sa.String(length=80), nullable=False, unique=True),
        sa.Column("provider", sa.String(length=50), nullable=False, server_default="stub"),
        sa.Column("api_url", sa.String(length=500), nullable=True),
        sa.Column("api_key", sa.Text(), nullable=True),
        sa.Column("chat_model", sa.String(length=120), nullable=True),
        sa.Column("vision_model", sa.String(length=120), nullable=True),
        sa.Column("profile_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("llm_profiles")
