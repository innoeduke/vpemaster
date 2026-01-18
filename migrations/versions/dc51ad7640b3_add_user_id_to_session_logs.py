"""add user_id to session_logs

Revision ID: dc51ad7640b3
Revises: 26a80f67f9e7
Create Date: 2026-01-17 01:59:44.023690

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dc51ad7640b3'
down_revision = '26a80f67f9e7'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Check Session_Logs columns
    sl_columns = [c['name'] for c in inspector.get_columns('Session_Logs')]
    if 'user_id' not in sl_columns:
        # 1. Add user_id column
        op.add_column('Session_Logs', sa.Column('user_id', sa.Integer(), nullable=True))
        op.create_foreign_key('fk_session_logs_user', 'Session_Logs', 'Users', ['user_id'], ['id'], ondelete='SET NULL')

    # 2. Data Migration: Update user_id based on Owner_ID -> Contact_ID mapping
    # Only if Users have Contact_ID
    u_columns = [c['name'] for c in inspector.get_columns('Users')]
    has_contact_id = any(c.lower() == 'contact_id' for c in u_columns)
    
    if has_contact_id:
        # SQLite/MySQL compatible update
        conn.execute(sa.text("""
            UPDATE Session_Logs sl
            JOIN Users u ON sl.Owner_ID = u.Contact_ID
            SET sl.user_id = u.id
            WHERE sl.Owner_ID IS NOT NULL
        """))


def downgrade():
    # Remove foreign key and column
    op.drop_constraint('fk_session_logs_user', 'Session_Logs', type_='foreignkey')
    op.drop_column('Session_Logs', 'user_id')
