"""drop_user_roles_table

Revision ID: f12ff9454119
Revises: f0145f9f8559
Create Date: 2026-01-17 13:52:04.690160

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f12ff9454119'
down_revision = 'f0145f9f8559'
branch_labels = None
depends_on = None


def upgrade():
    # Add foreign key constraint to user_clubs.club_role_id if not exists
    with op.batch_alter_table('user_clubs', schema=None) as batch_op:
        # Check if the constraint exists before adding
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        fks = inspector.get_foreign_keys('user_clubs')
        fk_exists = any(fk['constrained_columns'] == ['club_role_id'] for fk in fks)
        
        if not fk_exists:
            batch_op.create_foreign_key(
                'fk_user_clubs_club_role_id',
                'auth_roles',
                ['club_role_id'],
                ['id'],
                ondelete='SET NULL'
            )
    
    # Drop user_roles table
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    
    if 'user_roles' in tables:
        op.drop_table('user_roles')


def downgrade():
    # Recreate user_roles table
    op.create_table(
        'user_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_id', sa.Integer(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.Column('assigned_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['role_id'], ['auth_roles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['Users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['assigned_by'], ['Users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'role_id', name='unique_user_role')
    )
    
    # Remove foreign key from user_clubs.club_role_id
    with op.batch_alter_table('user_clubs', schema=None) as batch_op:
        batch_op.drop_constraint('fk_user_clubs_club_role_id', type_='foreignkey')
