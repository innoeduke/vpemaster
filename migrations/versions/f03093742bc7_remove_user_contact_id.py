"""remove_user_contact_id

Revision ID: f03093742bc7
Revises: 49aea4a0b902
Create Date: 2026-01-18 01:39:06.422673

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f03093742bc7'
down_revision = '49aea4a0b902'
branch_labels = None
depends_on = None


def upgrade():
    # Check if users.contact_id exists before trying to use it
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]
    
    # 1. Backfill user_clubs.contact_id from users.contact_id only if the column exists
    if 'contact_id' in columns:
        op.execute("""
            UPDATE user_clubs 
            JOIN users ON user_clubs.user_id = users.id 
            SET user_clubs.contact_id = users.contact_id 
            WHERE user_clubs.contact_id IS NULL AND users.contact_id IS NOT NULL
        """)
        
        # 2. Drop foreign key and column from users table
        with op.batch_alter_table('users', schema=None) as batch_op:
            try:
                batch_op.drop_constraint('Users_ibfk_1', type_='foreignkey')
            except Exception:
                pass  # Constraint might not exist
            
            try:
                batch_op.drop_index('Contact_ID')  # DROP UNIQUE INDEX if exists
            except Exception:
                pass  # Index might not exist
            
            batch_op.drop_column('contact_id')


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('contact_id', sa.Integer(), nullable=True))
        batch_op.create_unique_constraint('Contact_ID', ['contact_id'])
        batch_op.create_foreign_key('Users_ibfk_1', 'Contacts', ['contact_id'], ['id'])
    
    # Backfill users.contact_id from user_clubs (best effort)
    op.execute("""
        UPDATE users
        JOIN user_clubs ON users.id = user_clubs.user_id
        SET users.contact_id = user_clubs.contact_id
        WHERE users.contact_id IS NULL AND user_clubs.contact_id IS NOT NULL
    """)
