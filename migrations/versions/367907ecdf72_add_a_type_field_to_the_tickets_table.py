"""add a type field to the tickets table

Revision ID: 367907ecdf72
Revises: 4390b0c7464c
Create Date: 2026-03-06 11:29:59.021778

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '367907ecdf72'
down_revision = '4390b0c7464c'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('tickets')]
    indexes = [i['name'] for i in inspector.get_indexes('tickets')]

    with op.batch_alter_table('tickets', schema=None) as batch_op:
        if 'type' not in columns:
            batch_op.add_column(sa.Column('type', sa.String(length=50), nullable=True))
        if 'uq_tickets_name' in indexes:
            batch_op.drop_index(batch_op.f('uq_tickets_name'))

    # ### end Alembic commands ###


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('tickets')]
    indexes = [i['name'] for i in inspector.get_indexes('tickets')]

    with op.batch_alter_table('tickets', schema=None) as batch_op:
        if 'uq_tickets_name' not in indexes:
            batch_op.create_index(batch_op.f('uq_tickets_name'), ['name'], unique=True)
        if 'type' in columns:
            batch_op.drop_column('type')

    # ### end Alembic commands ###
