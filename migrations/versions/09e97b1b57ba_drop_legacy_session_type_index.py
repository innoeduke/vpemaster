"""drop legacy session type index

Revision ID: 09e97b1b57ba
Revises: 9d6de2854377
Create Date: 2026-01-30 01:54:40.639095

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '09e97b1b57ba'
down_revision = '9d6de2854377'
branch_labels = None
depends_on = None


def upgrade():
    # Use inspector to check for index existence before dropping
    conn = op.get_bind()
    from sqlalchemy.engine.reflection import Inspector
    inspector = Inspector.from_engine(conn)
    indexes = [i['name'] for i in inspector.get_indexes('Session_Types')]
    
    if 'uq_Session_Types_Title' in indexes:
        with op.batch_alter_table('Session_Types', schema=None) as batch_op:
            batch_op.drop_index('uq_Session_Types_Title')
    elif 'uq_session_types_title' in indexes: # Check for lower case just in case
        with op.batch_alter_table('Session_Types', schema=None) as batch_op:
            batch_op.drop_index('uq_session_types_title')


def downgrade():
    # Attempt to restore the unique index if it was dropped
    with op.batch_alter_table('Session_Types', schema=None) as batch_op:
        batch_op.create_index('uq_Session_Types_Title', ['Title'], unique=True)
