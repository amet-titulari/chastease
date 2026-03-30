"""add_session_phase_state

Revision ID: 0032
Revises: 0031
Create Date: 2026-03-30 18:05:00
"""

from alembic import op
import sqlalchemy as sa
from app.services.secret_crypto import EncryptedText


revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(sa.Column("phase_state_json", EncryptedText(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_column("phase_state_json")
