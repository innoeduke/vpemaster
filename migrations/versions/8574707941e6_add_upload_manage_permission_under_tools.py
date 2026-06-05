"""add upload_manage permission under tools

Revision ID: 8574707941e6
Revises: a8adac27e283
Create Date: 2026-06-05 11:11:44.737868

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8574707941e6'
down_revision = 'a8adac27e283'
branch_labels = None
depends_on = None


def upgrade():
    from datetime import datetime, timezone
    conn = op.get_bind()
    
    # 1. Add UPLOAD_MANAGE permission
    existing = conn.execute(sa.text("SELECT id FROM permissions WHERE name = 'UPLOAD_MANAGE'")).fetchone()
    if not existing:
        conn.execute(
            sa.text("""
                INSERT INTO permissions (name, description, category, resource, action, created_at) 
                VALUES ('UPLOAD_MANAGE', 'Manage file uploads and upload links', 'tools', 'upload', 'manage', :created_at)
            """),
            {'created_at': datetime.now(timezone.utc)}
        )
    
    # 2. Assign UPLOAD_MANAGE to SysAdmin & ClubAdmin roles
    perm_row = conn.execute(sa.text("SELECT id FROM permissions WHERE name = 'UPLOAD_MANAGE'")).fetchone()
    if perm_row:
        pid = perm_row[0]
        for role_name in ['SysAdmin', 'ClubAdmin']:
            role_row = conn.execute(sa.text("SELECT id FROM auth_roles WHERE name = :role_name"), {'role_name': role_name}).fetchone()
            if role_row:
                rid = role_row[0]
                # Check if assignment exists
                exists = conn.execute(
                    sa.text("SELECT 1 FROM role_permissions WHERE role_id = :rid AND permission_id = :pid"),
                    {'rid': rid, 'pid': pid}
                ).fetchone()
                
                if not exists:
                    conn.execute(
                        sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:rid, :pid)"),
                        {'rid': rid, 'pid': pid}
                    )


def downgrade():
    conn = op.get_bind()
    
    # 1. Remove role assignments first due to FK constraints
    perm_row = conn.execute(sa.text("SELECT id FROM permissions WHERE name = 'UPLOAD_MANAGE'")).fetchone()
    if perm_row:
        pid = perm_row[0]
        conn.execute(sa.text("DELETE FROM role_permissions WHERE permission_id = :pid"), {'pid': pid})
    
    # 2. Remove permission
    conn.execute(sa.text("DELETE FROM permissions WHERE name = 'UPLOAD_MANAGE'"))
