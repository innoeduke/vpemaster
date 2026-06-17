"""add meeting poster_url

Revision ID: 4154ec1126cf
Revises: 502a72bf7bc4
Create Date: 2026-06-17 14:48:31.319872

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4154ec1126cf'
down_revision = '502a72bf7bc4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('Meetings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('poster_url', sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table('Meetings', schema=None) as batch_op:
        batch_op.drop_column('poster_url')
