"""add hygiene quota fields to sessions

Revision ID: 20260310_0008
Revises: 20260310_0007
Create Date: 2026-03-10 00:08:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260310_0008"
down_revision = "20260310_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(sa.Column("hygiene_limit_daily", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("hygiene_limit_weekly", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("hygiene_limit_monthly", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_column("hygiene_limit_monthly")
        batch_op.drop_column("hygiene_limit_weekly")
        batch_op.drop_column("hygiene_limit_daily")
