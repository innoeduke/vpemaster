"""add_quantity_to_roster

Revision ID: e4f053c6e5d3
Revises: e6a9da78bcff
Create Date: 2026-05-25 15:05:05.452929

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'e4f053c6e5d3'
down_revision = 'e6a9da78bcff'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('roster', schema=None) as batch_op:
        batch_op.add_column(sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'))


def downgrade():
    with op.batch_alter_table('roster', schema=None) as batch_op:
        batch_op.drop_column('quantity')
