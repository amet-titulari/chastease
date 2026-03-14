"""add persona task library table

Revision ID: 0015
Revises: 0014
Create Date: 2026-03-17
"""

from alembic import op
import sqlalchemy as sa


revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persona_task_templates",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("persona_id", sa.Integer(), sa.ForeignKey("personas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("deadline_minutes", sa.Integer(), nullable=True),
        sa.Column("requires_verification", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("verification_criteria", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_persona_task_templates_persona_id", "persona_task_templates", ["persona_id"])


def downgrade() -> None:
    op.drop_index("ix_persona_task_templates_persona_id", table_name="persona_task_templates")
    op.drop_table("persona_task_templates")