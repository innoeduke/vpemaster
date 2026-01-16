"""add_about_club_permissions

Revision ID: 7fc8186e5275
Revises: c149e90eeb0e
Create Date: 2026-01-16 16:20:52.621864

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7fc8186e5275'
down_revision = 'c149e90eeb0e'
branch_labels = None
depends_on = None


def upgrade():
    """Add ABOUT_CLUB_VIEW and ABOUT_CLUB_EDIT permissions."""
    conn = op.get_bind()
    
    # 1. Insert ABOUT_CLUB_VIEW permission if it doesn't exist
    conn.execute(sa.text("""
        INSERT INTO permissions (name, description, category, resource, action, created_at)
        SELECT 'ABOUT_CLUB_VIEW', 
               'View club information and executive committee',
               'club',
               'club',
               'view',
               CURRENT_TIMESTAMP
        WHERE NOT EXISTS (
            SELECT 1 FROM permissions WHERE name = 'ABOUT_CLUB_VIEW'
        )
    """))
    
    # 2. Insert ABOUT_CLUB_EDIT permission if it doesn't exist
    conn.execute(sa.text("""
        INSERT INTO permissions (name, description, category, resource, action, created_at)
        SELECT 'ABOUT_CLUB_EDIT',
               'Edit club information and executive committee',
               'club',
               'club',
               'edit',
               CURRENT_TIMESTAMP
        WHERE NOT EXISTS (
            SELECT 1 FROM permissions WHERE name = 'ABOUT_CLUB_EDIT'
        )
    """))
    
    # 3. Assign ABOUT_CLUB_VIEW to all roles (SysAdmin, ClubAdmin, Staff, User)
    conn.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM auth_roles r
        CROSS JOIN permissions p
        WHERE p.name = 'ABOUT_CLUB_VIEW'
        AND NOT EXISTS (
            SELECT 1 FROM role_permissions rp
            WHERE rp.role_id = r.id AND rp.permission_id = p.id
        )
    """))
    
    # 4. Assign ABOUT_CLUB_EDIT to admin roles (SysAdmin, ClubAdmin)
    conn.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM auth_roles r
        CROSS JOIN permissions p
        WHERE p.name = 'ABOUT_CLUB_EDIT'
        AND r.name IN ('SysAdmin', 'ClubAdmin')
        AND NOT EXISTS (
            SELECT 1 FROM role_permissions rp
            WHERE rp.role_id = r.id AND rp.permission_id = p.id
        )
    """))


def downgrade():
    """Remove ABOUT_CLUB permissions."""
    conn = op.get_bind()
    
    # Delete role-permission associations first (due to foreign keys)
    conn.execute(sa.text("""
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions 
            WHERE name IN ('ABOUT_CLUB_VIEW', 'ABOUT_CLUB_EDIT')
        )
    """))
    
    # Delete the permissions
    conn.execute(sa.text("""
        DELETE FROM permissions
        WHERE name IN ('ABOUT_CLUB_VIEW', 'ABOUT_CLUB_EDIT')
    """))
