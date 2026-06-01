"""add chat permissions and seed

Revision ID: b4a20082afb8
Revises: d8a52466d161
Create Date: 2026-06-02 01:38:11.861806

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4a20082afb8'
down_revision = 'd8a52466d161'
branch_labels = None
depends_on = None


def upgrade():
    from datetime import datetime, timezone
    conn = op.get_bind()

    # 1. Add/Update CHAT_COMMANDS permission
    existing_cmd = conn.execute(sa.text("SELECT id FROM permissions WHERE name = 'CHAT_COMMANDS'")).fetchone()
    if not existing_cmd:
        conn.execute(
            sa.text("""
                INSERT INTO permissions (name, description, category, resource, action, created_at) 
                VALUES ('CHAT_COMMANDS', 'Allow using chat terminal commands', 'Chat', 'chat', 'commands', :created_at)
            """),
            {'created_at': datetime.now(timezone.utc)}
        )
    else:
        conn.execute(
            sa.text("""
                UPDATE permissions 
                SET category = 'Chat', resource = 'chat', action = 'commands', description = 'Allow using chat terminal commands'
                WHERE name = 'CHAT_COMMANDS'
            """)
        )

    # 2. Add/Update CHAT_AI permission
    existing_ai = conn.execute(sa.text("SELECT id FROM permissions WHERE name = 'CHAT_AI'")).fetchone()
    if not existing_ai:
        conn.execute(
            sa.text("""
                INSERT INTO permissions (name, description, category, resource, action, created_at) 
                VALUES ('CHAT_AI', 'Allow talking to AI Assistant using LLM', 'Chat', 'chat', 'ai', :created_at)
            """),
            {'created_at': datetime.now(timezone.utc)}
        )
    else:
        conn.execute(
            sa.text("""
                UPDATE permissions 
                SET category = 'Chat', resource = 'chat', action = 'ai', description = 'Allow talking to AI Assistant using LLM'
                WHERE name = 'CHAT_AI'
            """)
        )

    # 3. Get SysAdmin Role ID and assign permissions
    role_row = conn.execute(sa.text("SELECT id FROM auth_roles WHERE name = 'SysAdmin'")).fetchone()
    if role_row:
        rid = role_row[0]
        
        cmd_perm = conn.execute(sa.text("SELECT id FROM permissions WHERE name = 'CHAT_COMMANDS'")).fetchone()
        ai_perm = conn.execute(sa.text("SELECT id FROM permissions WHERE name = 'CHAT_AI'")).fetchone()
        
        for perm in [cmd_perm, ai_perm]:
            if perm:
                pid = perm[0]
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
    cmd_perm = conn.execute(sa.text("SELECT id FROM permissions WHERE name = 'CHAT_COMMANDS'")).fetchone()
    ai_perm = conn.execute(sa.text("SELECT id FROM permissions WHERE name = 'CHAT_AI'")).fetchone()
    
    for perm in [cmd_perm, ai_perm]:
        if perm:
            pid = perm[0]
            conn.execute(sa.text("DELETE FROM role_permissions WHERE permission_id = :pid"), {'pid': pid})
            
    conn.execute(sa.text("DELETE FROM permissions WHERE name IN ('CHAT_COMMANDS', 'CHAT_AI')"))
