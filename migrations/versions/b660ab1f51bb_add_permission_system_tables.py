"""add_permission_system_tables

Revision ID: b660ab1f51bb
Revises: 14e9302a2d45
Create Date: 2026-01-15 15:38:15.586286

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'b660ab1f51bb'
down_revision = '14e9302a2d45'
branch_labels = None
depends_on = None


# Permission and role data from existing ROLE_PERMISSIONS mapping
ROLE_PERMISSIONS_DATA = {
    "Admin": {
        "AGENDA_EDIT", "AGENDA_VIEW",
        "BOOKING_ASSIGN_ALL", "BOOKING_BOOK_OWN",
        "SPEECH_LOGS_EDIT_ALL", "SPEECH_LOGS_VIEW_ALL",
        "PATHWAY_LIB_EDIT", "PATHWAY_LIB_VIEW",
        "CONTACT_BOOK_EDIT", "CONTACT_BOOK_VIEW",
        "SETTINGS_EDIT_ALL", "SETTINGS_VIEW_ALL",
        "ACHIEVEMENTS_EDIT", "ACHIEVEMENTS_VIEW",
        "VOTING_VIEW_RESULTS",
        "VOTING_TRACK_PROGRESS",
        "ROSTER_VIEW"
    },
    "VPE": {
        "AGENDA_EDIT", "AGENDA_VIEW",
        "BOOKING_ASSIGN_ALL", "BOOKING_BOOK_OWN",
        "SPEECH_LOGS_EDIT_ALL", "SPEECH_LOGS_VIEW_ALL",
        "PATHWAY_LIB_EDIT", "PATHWAY_LIB_VIEW",
        "CONTACT_BOOK_EDIT", "CONTACT_BOOK_VIEW",
        "SETTINGS_VIEW_ALL",
        "ACHIEVEMENTS_EDIT", "ACHIEVEMENTS_VIEW",
        "VOTING_VIEW_RESULTS",
        "ROSTER_VIEW"
    },
    "Officer": {
        "AGENDA_VIEW",
        "BOOKING_BOOK_OWN",
        "SPEECH_LOGS_VIEW_ALL",
        "CONTACT_BOOK_VIEW",
        "PATHWAY_LIB_VIEW",
        "ACHIEVEMENTS_VIEW",
        "VOTING_VIEW_RESULTS",
    },
    "Member": {
        "AGENDA_VIEW",
        "BOOKING_BOOK_OWN",
        "SPEECH_LOGS_VIEW_OWN",
        "PATHWAY_LIB_VIEW",
    },
}

# Permission metadata (category, resource, action)
PERMISSION_METADATA = {
    "AGENDA_EDIT": ("agenda", "agenda", "edit"),
    "AGENDA_VIEW": ("agenda", "agenda", "view"),
    "BOOKING_ASSIGN_ALL": ("booking", "booking", "assign_all"),
    "BOOKING_BOOK_OWN": ("booking", "booking", "book_own"),
    "SPEECH_LOGS_EDIT_ALL": ("speech_logs", "speech_logs", "edit_all"),
    "SPEECH_LOGS_VIEW_ALL": ("speech_logs", "speech_logs", "view_all"),
    "SPEECH_LOGS_VIEW_OWN": ("speech_logs", "speech_logs", "view_own"),
    "PATHWAY_LIB_EDIT": ("pathways", "pathway_library", "edit"),
    "PATHWAY_LIB_VIEW": ("pathways", "pathway_library", "view"),
    "CONTACT_BOOK_EDIT": ("contacts", "contact_book", "edit"),
    "CONTACT_BOOK_VIEW": ("contacts", "contact_book", "view"),
    "SETTINGS_EDIT_ALL": ("settings", "settings", "edit_all"),
    "SETTINGS_VIEW_ALL": ("settings", "settings", "view_all"),
    "ACHIEVEMENTS_EDIT": ("achievements", "achievements", "edit"),
    "ACHIEVEMENTS_VIEW": ("achievements", "achievements", "view"),
    "VOTING_VIEW_RESULTS": ("voting", "voting", "view_results"),
    "VOTING_TRACK_PROGRESS": ("voting", "voting", "track_progress"),
    "ROSTER_VIEW": ("roster", "roster", "view"),
}

# Role hierarchy levels
ROLE_LEVELS = {
    "Admin": 8,
    "VPE": 4,
    "Officer": 2,
    "Member": 1,
}


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # Create permissions table if not exists
    if 'permissions' not in existing_tables:
        op.create_table(
            'permissions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('category', sa.String(length=50), nullable=True),
            sa.Column('resource', sa.String(length=50), nullable=True),
            sa.Column('action', sa.String(length=50), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
        op.create_index(op.f('ix_permissions_name'), 'permissions', ['name'], unique=False)
        op.create_index(op.f('ix_permissions_category'), 'permissions', ['category'], unique=False)
    
    # Create auth_roles table if not exists
    if 'auth_roles' not in existing_tables:
        op.create_table(
            'auth_roles',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=50), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('level', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
        op.create_index(op.f('ix_auth_roles_name'), 'auth_roles', ['name'], unique=False)
    
    # Create role_permissions association table if not exists
    if 'role_permissions' not in existing_tables:
        op.create_table(
            'role_permissions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('role_id', sa.Integer(), nullable=False),
            sa.Column('permission_id', sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['role_id'], ['auth_roles.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('role_id', 'permission_id', name='unique_role_permission')
        )
    
    # Create user_roles association table if not exists
    if 'user_roles' not in existing_tables:
        op.create_table(
            'user_roles',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('role_id', sa.Integer(), nullable=False),
            sa.Column('assigned_at', sa.DateTime(), nullable=True),
            sa.Column('assigned_by', sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(['assigned_by'], ['Users.id'], ondelete='SET NULL'),
            sa.ForeignKeyConstraint(['role_id'], ['auth_roles.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['user_id'], ['Users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'role_id', name='unique_user_role')
        )
    
    # Seed permissions
    permissions_table = sa.table('permissions',
        sa.column('name', sa.String),
        sa.column('description', sa.Text),
        sa.column('category', sa.String),
        sa.column('resource', sa.String),
        sa.column('action', sa.String),
        sa.column('created_at', sa.DateTime)
    )
    
    # Collect all unique permissions
    all_permissions = set()
    for perms in ROLE_PERMISSIONS_DATA.values():
        all_permissions.update(perms)
    
    permission_rows = []
    for perm_name in sorted(all_permissions):
        category, resource, action = PERMISSION_METADATA.get(perm_name, (None, None, None))
        permission_rows.append({
            'name': perm_name,
            'description': f'Permission to {perm_name.lower().replace("_", " ")}',
            'category': category,
            'resource': resource,
            'action': action,
            'created_at': datetime.utcnow()
        })
    
    # Only seed if permissions table is empty
    existing_perms = conn.execute(sa.text("SELECT count(*) FROM permissions")).scalar()
    if existing_perms == 0:
        op.bulk_insert(permissions_table, permission_rows)
    
    # Seed roles
    roles_table = sa.table('auth_roles',
        sa.column('name', sa.String),
        sa.column('description', sa.Text),
        sa.column('level', sa.Integer),
        sa.column('created_at', sa.DateTime)
    )
    
    role_rows = []
    for role_name, level in ROLE_LEVELS.items():
        role_rows.append({
            'name': role_name,
            'description': f'{role_name} role',
            'level': level,
            'created_at': datetime.utcnow()
        })
    
    # Only seed if auth_roles table is empty
    existing_roles = conn.execute(sa.text("SELECT count(*) FROM auth_roles")).scalar()
    if existing_roles == 0:
        op.bulk_insert(roles_table, role_rows)
    
    # Seed role-permission mappings
    # Note: We need to query the IDs after insertion, so we'll use raw SQL
    conn = op.get_bind()
    
    for role_name, permissions in ROLE_PERMISSIONS_DATA.items():
        # Get role ID
        role_result = conn.execute(
            sa.text("SELECT id FROM auth_roles WHERE name = :name"),
            {"name": role_name}
        ).fetchone()
        
        if role_result:
            role_id = role_result[0]
            
            # Get permission IDs and insert mappings
            for perm_name in permissions:
                perm_result = conn.execute(
                    sa.text("SELECT id FROM permissions WHERE name = :name"),
                    {"name": perm_name}
                ).fetchone()
                
                if perm_result:
                    perm_id = perm_result[0]
                    # Check if mapping already exists
                    mapping_exists = conn.execute(
                        sa.text("SELECT 1 FROM role_permissions WHERE role_id = :role_id AND permission_id = :perm_id"),
                        {"role_id": role_id, "perm_id": perm_id}
                    ).fetchone()
                    
                    if not mapping_exists:
                        conn.execute(
                            sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :perm_id)"),
                            {"role_id": role_id, "perm_id": perm_id}
                        )
    
    # Migrate existing user roles to user_roles table
    users_result = conn.execute(sa.text("SELECT id, Role FROM Users WHERE Role IS NOT NULL"))
    
    for user_row in users_result:
        user_id, role_name = user_row
        
        # Get role ID
        role_result = conn.execute(
            sa.text("SELECT id FROM auth_roles WHERE name = :name"),
            {"name": role_name}
        ).fetchone()
        
        if role_result:
            role_id = role_result[0]
            # Check if user already has this role
            user_role_exists = conn.execute(
                sa.text("SELECT 1 FROM user_roles WHERE user_id = :user_id AND role_id = :role_id"),
                {"user_id": user_id, "role_id": role_id}
            ).fetchone()
            
            if not user_role_exists:
                conn.execute(
                    sa.text("INSERT INTO user_roles (user_id, role_id, assigned_at) VALUES (:user_id, :role_id, :assigned_at)"),
                    {"user_id": user_id, "role_id": role_id, "assigned_at": datetime.utcnow()}
                )


def downgrade():
    # Drop tables in reverse order
    op.drop_table('user_roles')
    op.drop_table('role_permissions')
    op.drop_index(op.f('ix_auth_roles_name'), table_name='auth_roles')
    op.drop_table('auth_roles')
    op.drop_index(op.f('ix_permissions_category'), table_name='permissions')
    op.drop_index(op.f('ix_permissions_name'), table_name='permissions')
    op.drop_table('permissions')
