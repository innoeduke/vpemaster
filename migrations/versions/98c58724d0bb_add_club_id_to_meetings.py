"""add_club_id_to_meetings

Revision ID: 98c58724d0bb
Revises: 7fc8186e5275
Create Date: 2026-01-16 17:18:27.122285

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '98c58724d0bb'
down_revision = '7fc8186e5275'
branch_labels = None
depends_on = None


def upgrade():
    """Add club_id column to Meetings table and populate with default club."""
    from sqlalchemy import text, inspect
    
    # Get connection and inspector
    conn = op.get_bind()
    inspector = inspect(conn)
    
    # Check if club_id column already exists
    columns = [col['name'] for col in inspector.get_columns('Meetings')]
    column_exists = 'club_id' in columns
    
    # 1. Ensure at least one club exists
    result = conn.execute(text("SELECT id FROM clubs LIMIT 1"))
    club_row = result.fetchone()
    
    if not club_row:
        # Create a default club if none exists
        conn.execute(text("""
            INSERT INTO clubs (club_no, club_name, district, division, area, created_at, updated_at)
            VALUES ('000000', 'Default Club', 'Default District', 'Default Division', 'Default Area', NOW(), NOW())
        """))
        result = conn.execute(text("SELECT id FROM clubs LIMIT 1"))
        club_row = result.fetchone()
    
    default_club_id = club_row[0]
    
    if not column_exists:
        # 2. Add club_id column as nullable first
        with op.batch_alter_table('Meetings', schema=None) as batch_op:
            batch_op.add_column(sa.Column('club_id', sa.Integer(), nullable=True))
    
    # 3. Populate all existing meetings with the default club_id
    conn.execute(text(f"UPDATE Meetings SET club_id = {default_club_id} WHERE club_id IS NULL"))
    
    # 4. Make the column NOT NULL and add constraints (if not already done)
    with op.batch_alter_table('Meetings', schema=None) as batch_op:
        if not column_exists:
            batch_op.alter_column('club_id',
                                existing_type=sa.Integer(),
                                nullable=False)
        
        # Check if foreign key exists
        foreign_keys = [fk['name'] for fk in inspector.get_foreign_keys('Meetings')]
        if 'fk_meetings_club_id' not in foreign_keys:
            batch_op.create_foreign_key('fk_meetings_club_id', 'clubs', ['club_id'], ['id'])
        
        # Check if index exists
        indexes = [idx['name'] for idx in inspector.get_indexes('Meetings')]
        if 'ix_Meetings_club_id' not in indexes:
            batch_op.create_index(batch_op.f('ix_Meetings_club_id'), ['club_id'], unique=False)


def downgrade():
    """Remove club_id column from Meetings table."""
    with op.batch_alter_table('Meetings', schema=None) as batch_op:
        batch_op.drop_constraint('fk_meetings_club_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_Meetings_club_id'))
        batch_op.drop_column('club_id')
