"""add_first_name_last_name_to_contacts

Revision ID: 50ea78715e68
Revises: f12ff9454119
Create Date: 2026-01-17 14:40:50.837522

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '50ea78715e68'
down_revision = 'f12ff9454119'
branch_labels = None
depends_on = None


def upgrade():
    # Check if columns exist before adding them
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('Contacts')]
    
    # Add first_name and last_name columns only if they don't exist
    if 'first_name' not in columns:
        op.add_column('Contacts', sa.Column('first_name', sa.String(100), nullable=True))
    if 'last_name' not in columns:
        op.add_column('Contacts', sa.Column('last_name', sa.String(100), nullable=True))


def downgrade():
    # Remove first_name and last_name columns
    op.drop_column('Contacts', 'last_name')
    op.drop_column('Contacts', 'first_name')
