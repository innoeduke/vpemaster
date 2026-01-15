from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'fa4966cc4756'
down_revision = 'daec7f3551bf'
branch_labels = None
depends_on = None


def get_fk_names(table_name, referred_table, connection):
    inspector = inspect(connection)
    fks = inspector.get_foreign_keys(table_name)
    return [fk['name'] for fk in fks if fk['referred_table'] == referred_table]


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    # 1. Rename table 'roles' -> 'meeting_roles'
    if 'roles' in tables and 'meeting_roles' not in tables:
        op.rename_table('roles', 'meeting_roles')
    
    # Refresh tables list after potential rename
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    # 2. Update Foreign Keys for Session_Types
    if 'Session_Types' in tables:
        # Check if it currently points to 'roles' (needs update)
        fks_to_roles = get_fk_names('Session_Types', 'roles', conn)
        for fk_name in fks_to_roles:
            with op.batch_alter_table('Session_Types', schema=None) as batch_op:
                batch_op.drop_constraint(fk_name, type_='foreignkey')
        
        # Ensure it points to 'meeting_roles'
        fks_to_meeting_roles = get_fk_names('Session_Types', 'meeting_roles', conn)
        if not fks_to_meeting_roles and 'meeting_roles' in tables:
            with op.batch_alter_table('Session_Types', schema=None) as batch_op:
                batch_op.create_foreign_key(None, 'meeting_roles', ['role_id'], ['id'])

    # 3. Update Foreign Keys for roster_roles
    if 'roster_roles' in tables:
        # Check if it currently points to 'roles' (needs update)
        fks_to_roles = get_fk_names('roster_roles', 'roles', conn)
        for fk_name in fks_to_roles:
            with op.batch_alter_table('roster_roles', schema=None) as batch_op:
                batch_op.drop_constraint(fk_name, type_='foreignkey')
        
        # Ensure it points to 'meeting_roles'
        fks_to_meeting_roles = get_fk_names('roster_roles', 'meeting_roles', conn)
        if not fks_to_meeting_roles and 'meeting_roles' in tables:
            with op.batch_alter_table('roster_roles', schema=None) as batch_op:
                batch_op.create_foreign_key(None, 'meeting_roles', ['role_id'], ['id'])


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    # 1. Rename 'meeting_roles' -> 'roles'
    if 'meeting_roles' in tables and 'roles' not in tables:
        op.rename_table('meeting_roles', 'roles')
    
    # Refresh tables list after potential rename
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    # 2. Update Foreign Keys for roster_roles
    if 'roster_roles' in tables:
        # Points to meeting_roles? (needs revert)
        fks_to_meeting_roles = get_fk_names('roster_roles', 'meeting_roles', conn)
        for fk_name in fks_to_meeting_roles:
            with op.batch_alter_table('roster_roles', schema=None) as batch_op:
                batch_op.drop_constraint(fk_name, type_='foreignkey')
        
        # Ensure it points to 'roles'
        fks_to_roles = get_fk_names('roster_roles', 'roles', conn)
        if not fks_to_roles and 'roles' in tables:
            with op.batch_alter_table('roster_roles', schema=None) as batch_op:
                batch_op.create_foreign_key('roster_roles_ibfk_1', 'roles', ['role_id'], ['id'])

    # 3. Update Foreign Keys for Session_Types
    if 'Session_Types' in tables:
        # Points to meeting_roles? (needs revert)
        fks_to_meeting_roles = get_fk_names('Session_Types', 'meeting_roles', conn)
        for fk_name in fks_to_meeting_roles:
            with op.batch_alter_table('Session_Types', schema=None) as batch_op:
                batch_op.drop_constraint(fk_name, type_='foreignkey')
        
        # Ensure it points to 'roles'
        fks_to_roles = get_fk_names('Session_Types', 'roles', conn)
        if not fks_to_roles and 'roles' in tables:
            with op.batch_alter_table('Session_Types', schema=None) as batch_op:
                batch_op.create_foreign_key('Session_Types_ibfk_1', 'roles', ['role_id'], ['id'])
