"""empty message

Revision ID: 1954ce529fd3
Revises: 
Create Date: 2024-01-13 14:40:13.593039

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1954ce529fd3'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('benutzer',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=100), nullable=True),
    sa.Column('role', sa.String(length=100), nullable=True),
    sa.Column('avatarUrl', sa.String(length=100), nullable=True),
    sa.Column('lock_uuid', sa.String(length=128), nullable=True),
    sa.Column('CA_username', sa.String(length=128), nullable=True),
    sa.Column('CA_keyholdername', sa.String(length=128), nullable=True),
    sa.Column('CA_keyholder_id', sa.String(length=128), nullable=True),
    sa.Column('CA_user_id', sa.String(length=128), nullable=True),
    sa.Column('CA_lock_id', sa.String(length=128), nullable=True),
    sa.Column('CA_lock_status', sa.String(length=16), nullable=True),
    sa.Column('CA_combination_id', sa.String(length=128), nullable=True),
    sa.Column('TTL_username', sa.String(length=128), nullable=True),
    sa.Column('TTL_password_md5', sa.String(length=128), nullable=True),
    sa.Column('TTL_lock_alias', sa.String(length=128), nullable=True),
    sa.Column('TTL_lock_id', sa.String(length=128), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('username')
    )
    op.create_table('ca__lock__history',
    sa.Column('hist_id', sa.String(length=128), nullable=False),
    sa.Column('benutzer_id', sa.Integer(), nullable=False),
    sa.Column('lock_id', sa.String(length=128), nullable=True),
    sa.Column('type', sa.String(length=128), nullable=True),
    sa.Column('created_at', sa.String(length=128), nullable=True),
    sa.Column('extension', sa.String(length=128), nullable=True),
    sa.Column('title', sa.String(length=128), nullable=True),
    sa.Column('description', sa.String(length=128), nullable=True),
    sa.Column('icon', sa.String(length=128), nullable=True),
    sa.ForeignKeyConstraint(['benutzer_id'], ['benutzer.id'], ),
    sa.PrimaryKeyConstraint('hist_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('ca__lock__history')
    op.drop_table('benutzer')
    # ### end Alembic commands ###