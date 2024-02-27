"""empty message

Revision ID: c72c4a2b699b
Revises: a22bacdda53e
Create Date: 2024-02-27 14:41:18.694109

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c72c4a2b699b'
down_revision = 'a22bacdda53e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('chaster_session')
    with op.batch_alter_table('benutzer', schema=None) as batch_op:
        batch_op.add_column(sa.Column('TTL_gateway_id', sa.String(length=128), nullable=True))
        batch_op.drop_column('TTL_lock_alias')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('benutzer', schema=None) as batch_op:
        batch_op.add_column(sa.Column('TTL_lock_alias', sa.VARCHAR(length=128), nullable=True))
        batch_op.drop_column('TTL_gateway_id')

    op.create_table('chaster_session',
    sa.Column('id', sa.VARCHAR(length=64), nullable=False),
    sa.Column('user_id', sa.INTEGER(), nullable=False),
    sa.Column('username', sa.VARCHAR(length=100), nullable=True),
    sa.Column('keyholder_id', sa.INTEGER(), nullable=True),
    sa.Column('lock_uuid', sa.VARCHAR(length=128), nullable=True),
    sa.Column('lock_id', sa.VARCHAR(length=128), nullable=True),
    sa.Column('lock_status', sa.VARCHAR(length=16), nullable=True),
    sa.Column('combination_id', sa.VARCHAR(length=128), nullable=True),
    sa.Column('TTL_username', sa.VARCHAR(length=128), nullable=True),
    sa.Column('TTL_password_md5', sa.VARCHAR(length=128), nullable=True),
    sa.Column('TTL_lock_alias', sa.VARCHAR(length=128), nullable=True),
    sa.Column('TTL_lock_id', sa.VARCHAR(length=128), nullable=True),
    sa.ForeignKeyConstraint(['keyholder_id'], ['benutzer.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['benutzer.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('username')
    )
    # ### end Alembic commands ###
