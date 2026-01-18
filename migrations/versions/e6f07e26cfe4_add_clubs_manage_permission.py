"""add clubs_manage permission

Revision ID: e6f07e26cfe4
Revises: f03093742bc7
Create Date: 2026-01-18 14:43:58.876127

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e6f07e26cfe4'
down_revision = 'f03093742bc7'
branch_labels = None
depends_on = None


def upgrade():
    from datetime import datetime, timezone
    conn = op.get_bind()
    
    # 1. Add CLUBS_MANAGE permission
    existing = conn.execute(sa.text("SELECT id FROM permissions WHERE name = 'CLUBS_MANAGE'")).fetchone()
    if not existing:
        conn.execute(
            sa.text("""
                INSERT INTO permissions (name, description, category, resource, action, created_at) 
                VALUES ('CLUBS_MANAGE', 'Manage all clubs features', 'club', 'club', 'manage', :created_at)
            """),
            {'created_at': datetime.now(timezone.utc)}
        )
    
    # 2. Get Permission ID and SysAdmin Role ID
    perm_row = conn.execute(sa.text("SELECT id FROM permissions WHERE name = 'CLUBS_MANAGE'")).fetchone()
    role_row = conn.execute(sa.text("SELECT id FROM auth_roles WHERE name = 'SysAdmin'")).fetchone()
    
    if perm_row and role_row:
        pid = perm_row[0]
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
    # Remove assignment first due to FKs
    perm_row = conn.execute(sa.text("SELECT id FROM permissions WHERE name = 'CLUBS_MANAGE'")).fetchone()
    if perm_row:
        pid = perm_row[0]
        conn.execute(sa.text("DELETE FROM role_permissions WHERE permission_id = :pid"), {'pid': pid})
    
    # Remove permission
    conn.execute(sa.text("DELETE FROM permissions WHERE name = 'CLUBS_MANAGE'"))
