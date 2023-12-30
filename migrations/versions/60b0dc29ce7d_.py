"""empty message

Revision ID: 60b0dc29ce7d
Revises: be2abe4755d1
Create Date: 2023-12-30 18:11:54.239069

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '60b0dc29ce7d'
down_revision = 'be2abe4755d1'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('benutzer_config', schema=None) as batch_op:
        batch_op.add_column(sa.Column('CA_keyholdername_id', sa.String(length=128), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('benutzer_config', schema=None) as batch_op:
        batch_op.drop_column('CA_keyholdername_id')

    # ### end Alembic commands ###
