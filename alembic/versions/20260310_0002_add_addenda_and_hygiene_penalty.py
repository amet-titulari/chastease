"""add contract addenda and hygiene penalty fields

Revision ID: 20260310_0002
Revises: 20260310_0001
Create Date: 2026-03-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260310_0002"
down_revision = "20260310_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contract_addenda",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contract_id", sa.Integer(), sa.ForeignKey("contracts.id"), nullable=False),
        sa.Column("proposed_changes_json", sa.Text(), nullable=False),
        sa.Column("change_description", sa.Text(), nullable=False),
        sa.Column("proposed_by", sa.String(length=20), nullable=False, server_default="ai"),
        sa.Column("player_consent", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("player_consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.add_column(
        "hygiene_openings",
        sa.Column("penalty_seconds", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "hygiene_openings",
        sa.Column("penalty_applied_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("hygiene_openings", "penalty_applied_at")
    op.drop_column("hygiene_openings", "penalty_seconds")
    op.drop_table("contract_addenda")
