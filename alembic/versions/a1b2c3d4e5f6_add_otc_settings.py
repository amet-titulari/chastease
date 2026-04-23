"""add_otc_settings

Revision ID: a1b2c3d4e5f6
Revises: 70237ed937a5
Create Date: 2026-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '70237ed937a5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'otc_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('singleton_key', sa.String(length=32), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('otc_url', sa.String(length=512), nullable=True),
        sa.Column('channel', sa.String(length=4), nullable=False),
        sa.Column('intensity_fail', sa.Integer(), nullable=False),
        sa.Column('intensity_penalty', sa.Integer(), nullable=False),
        sa.Column('intensity_pass', sa.Integer(), nullable=False),
        sa.Column('ticks_fail', sa.Integer(), nullable=False),
        sa.Column('ticks_penalty', sa.Integer(), nullable=False),
        sa.Column('ticks_pass', sa.Integer(), nullable=False),
        sa.Column('pattern_fail', sa.String(length=120), nullable=False),
        sa.Column('pattern_penalty', sa.String(length=120), nullable=False),
        sa.Column('pattern_pass', sa.String(length=120), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('singleton_key'),
    )
    op.create_index(op.f('ix_otc_settings_id'), 'otc_settings', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_otc_settings_id'), table_name='otc_settings')
    op.drop_table('otc_settings')
