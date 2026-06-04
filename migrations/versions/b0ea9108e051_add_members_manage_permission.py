"""add members_manage permission

Revision ID: b0ea9108e051
Revises: 2f830fef3c3a
Create Date: 2026-06-04 21:24:58.034578

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b0ea9108e051'
down_revision = '2f830fef3c3a'
branch_labels = None
depends_on = None


def upgrade():
    from datetime import datetime, timezone
    conn = op.get_bind()
    
    # 1. Update SPEECH_LOGS_MANAGE category to 'members'
    conn.execute(
        sa.text("UPDATE permissions SET category = 'members' WHERE name = 'SPEECH_LOGS_MANAGE'")
    )
    
    # 2. Add MEMBERS_MANAGE permission
    existing = conn.execute(sa.text("SELECT id FROM permissions WHERE name = 'MEMBERS_MANAGE'")).fetchone()
    if not existing:
        conn.execute(
            sa.text("""
                INSERT INTO permissions (name, description, category, resource, action, created_at) 
                VALUES ('MEMBERS_MANAGE', 'Manage members and user accounts', 'members', 'members', 'manage', :created_at)
            """),
            {'created_at': datetime.now(timezone.utc)}
        )
    
    # 3. Get Permission ID and SysAdmin & ClubAdmin Role IDs
    perm_row = conn.execute(sa.text("SELECT id FROM permissions WHERE name = 'MEMBERS_MANAGE'")).fetchone()
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
    
    # 1. Revert SPEECH_LOGS_MANAGE category to 'speech_logs'
    conn.execute(
        sa.text("UPDATE permissions SET category = 'speech_logs' WHERE name = 'SPEECH_LOGS_MANAGE'")
    )
    
    # 2. Remove assignment first due to FKs
    perm_row = conn.execute(sa.text("SELECT id FROM permissions WHERE name = 'MEMBERS_MANAGE'")).fetchone()
    if perm_row:
        pid = perm_row[0]
        conn.execute(sa.text("DELETE FROM role_permissions WHERE permission_id = :pid"), {'pid': pid})
    
    # 3. Remove permission
    conn.execute(sa.text("DELETE FROM permissions WHERE name = 'MEMBERS_MANAGE'"))

