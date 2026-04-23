"""add otc continuous stimulus columns

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-23 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("otc_settings") as batch_op:
        batch_op.add_column(sa.Column("intensity_continuous", sa.Integer(), nullable=False, server_default="30"))
        batch_op.add_column(sa.Column("ticks_continuous", sa.Integer(), nullable=False, server_default="50"))
        batch_op.add_column(sa.Column("pattern_continuous", sa.String(120), nullable=False, server_default="经典"))


def downgrade() -> None:
    with op.batch_alter_table("otc_settings") as batch_op:
        batch_op.drop_column("intensity_continuous")
        batch_op.drop_column("ticks_continuous")
        batch_op.drop_column("pattern_continuous")
