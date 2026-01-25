"""rename is_distinct to has_single_owner

Revision ID: 90ce9be2b3f8
Revises: 7ce85929b05f
Create Date: 2026-01-23 17:33:54.180555

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '90ce9be2b3f8'
down_revision = '7ce85929b05f'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('meeting_roles')]
    
    if 'is_distinct' in columns:
        with op.batch_alter_table('meeting_roles', schema=None) as batch_op:
            batch_op.alter_column('is_distinct', new_column_name='has_single_owner', existing_type=sa.Boolean(), nullable=False)

    # ### end Alembic commands ###


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('meeting_roles')]
    
    if 'has_single_owner' in columns:
        with op.batch_alter_table('meeting_roles', schema=None) as batch_op:
            batch_op.alter_column('has_single_owner', new_column_name='is_distinct', existing_type=sa.Boolean(), nullable=False)
