"""fix user_clubs foreign key case

Revision ID: f68363777405
Revises: 603a9a419abf
Create Date: 2026-02-12 15:31:55.151825

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f68363777405'
down_revision = '603a9a419abf'
branch_labels = None
depends_on = None


def upgrade():
    # Fix the case-sensitivity issue for the user_id foreign key in user_clubs table.
    # On Linux, referencing 'Users' (uppercase) when the table is 'users' (lowercase)
    # causes an IntegrityError even if the ID exists.
    
    # 1. Drop the existing constraint with the incorrect case reference
    # Note: We use the existing name found in the production logs.
    op.drop_constraint('fk_user_clubs_user_id_Users', 'user_clubs', type_='foreignkey')
    
    # 2. Re-add the constraint pointing to the correct lowercase 'users' table
    op.create_foreign_key(
        'fk_user_clubs_user_id_users',
        'user_clubs', 'users',
        ['user_id'], ['id'],
        ondelete='CASCADE'
    )


def downgrade():
    # Revert to the uppercase reference if needed
    op.drop_constraint('fk_user_clubs_user_id_users', 'user_clubs', type_='foreignkey')
    op.create_foreign_key(
        'fk_user_clubs_user_id_Users',
        'user_clubs', 'Users',
        ['user_id'], ['id'],
        ondelete='CASCADE'
    )
