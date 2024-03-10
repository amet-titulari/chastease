"""empty message

Revision ID: 2f31cb980a4e
Revises: c72c4a2b699b
Create Date: 2024-03-10 12:23:52.885175

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2f31cb980a4e'
down_revision = 'c72c4a2b699b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('benutzer', schema=None) as batch_op:
        batch_op.add_column(sa.Column('CA_refresh_token', sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('TTL_refresh_token', sa.String(length=128), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('benutzer', schema=None) as batch_op:
        batch_op.drop_column('TTL_refresh_token')
        batch_op.drop_column('CA_refresh_token')

    # ### end Alembic commands ###
