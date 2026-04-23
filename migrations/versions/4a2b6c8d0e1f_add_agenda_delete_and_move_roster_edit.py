"""add agenda_delete permission and move roster_edit category

Revision ID: 4a2b6c8d0e1f
Revises: a1b2c3d4e5f6
Create Date: 2026-04-23 13:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone


# revision identifiers, used by Alembic.
revision = '4a2b6c8d0e1f'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    # 1. Add permissions
    permissions = [
        ('AGENDA_DELETE', 'Allow deleting a meeting', 'agenda', 'agenda', 'delete'),
        ('AGENDA_CREATE', 'Allow creating a new meeting', 'agenda', 'agenda', 'create')
    ]
    
    for name, desc, cat, res, act in permissions:
        existing = conn.execute(sa.text("SELECT id FROM permissions WHERE name = :name"), {'name': name}).fetchone()
        if not existing:
            conn.execute(
                sa.text("""
                    INSERT INTO permissions (name, description, category, resource, action, created_at) 
                    VALUES (:name, :description, :category, :resource, :action, :created_at)
                """),
                {'name': name, 'description': desc, 'category': cat, 'resource': res, 'action': act, 'created_at': datetime.now(timezone.utc)}
            )
    
    # 2. Assign to SysAdmin and ClubAdmin roles
    for name, _, _, _, _ in permissions:
        perm_row = conn.execute(sa.text("SELECT id FROM permissions WHERE name = :name"), {'name': name}).fetchone()
        if perm_row:
            pid = perm_row[0]
            for role_name in ['SysAdmin', 'ClubAdmin']:
                role_row = conn.execute(sa.text("SELECT id FROM auth_roles WHERE name = :name"), {'name': role_name}).fetchone()
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

    # 3. Move ROSTER_EDIT from 'club' to 'roster' category
    conn.execute(sa.text("UPDATE permissions SET category = 'roster' WHERE name = 'ROSTER_EDIT' AND category = 'club'"))


def downgrade():
    conn = op.get_bind()
    
    # 1. Revert ROSTER_EDIT category
    conn.execute(sa.text("UPDATE permissions SET category = 'club' WHERE name = 'ROSTER_EDIT' AND category = 'roster'"))

    # 2. Remove assignments
    for name in ['AGENDA_DELETE', 'AGENDA_CREATE']:
        perm_row = conn.execute(sa.text("SELECT id FROM permissions WHERE name = :name"), {'name': name}).fetchone()
        if perm_row:
            pid = perm_row[0]
            conn.execute(sa.text("DELETE FROM role_permissions WHERE permission_id = :pid"), {'pid': pid})
    
    # 3. Remove permissions
    conn.execute(sa.text("DELETE FROM permissions WHERE name IN ('AGENDA_DELETE', 'AGENDA_CREATE')"))
