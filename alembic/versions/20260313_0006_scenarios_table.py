"""add scenarios table

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-12
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenarios",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("key", sa.String(120), nullable=False, unique=True),
        sa.Column("character_ref", sa.String(120), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("lorebook_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("phases_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("scenarios")
