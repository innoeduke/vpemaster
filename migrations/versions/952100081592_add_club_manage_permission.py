"""add club_manage permission

Revision ID: 952100081592
Revises: 21b65b1b400c
Create Date: 2026-06-30 17:11:32.491554

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '952100081592'
down_revision = '21b65b1b400c'
branch_labels = None
depends_on = None


def upgrade():
    from datetime import datetime, timezone
    conn = op.get_bind()

    # 1. Add CLUB_MANAGE permission
    existing = conn.execute(
        sa.text("SELECT id FROM permissions WHERE name = 'CLUB_MANAGE'")
    ).fetchone()
    if not existing:
        conn.execute(
            sa.text("""
                INSERT INTO permissions (name, description, category, resource, action, created_at)
                VALUES ('CLUB_MANAGE',
                        'Manage club excomm and details',
                        'club', 'club', 'manage', :created_at)
            """),
            {'created_at': datetime.now(timezone.utc)}
        )

    # 2. Grant to ClubAdmin and Operator roles
    perm_row = conn.execute(
        sa.text("SELECT id FROM permissions WHERE name = 'CLUB_MANAGE'")
    ).fetchone()
    if not perm_row:
        return

    pid = perm_row[0]

    for role_name in ('ClubAdmin', 'Operator'):
        role_row = conn.execute(
            sa.text("SELECT id FROM auth_roles WHERE name = :name"),
            {'name': role_name}
        ).fetchone()

        if role_row:
            rid = role_row[0]
            clubs = conn.execute(
                sa.text("SELECT id FROM clubs WHERE status = 'active'")
            ).fetchall()
            for club_row in clubs:
                cid = club_row[0]
                exists = conn.execute(
                    sa.text("SELECT 1 FROM role_permissions WHERE role_id = :rid AND permission_id = :pid AND club_id = :cid"),
                    {'rid': rid, 'pid': pid, 'cid': cid}
                ).fetchone()

                if not exists:
                    conn.execute(
                        sa.text("INSERT INTO role_permissions (role_id, permission_id, club_id) VALUES (:rid, :pid, :cid)"),
                        {'rid': rid, 'pid': pid, 'cid': cid}
                    )


def downgrade():
    conn = op.get_bind()
    perm_row = conn.execute(
        sa.text("SELECT id FROM permissions WHERE name = 'CLUB_MANAGE'")
    ).fetchone()
    if perm_row:
        pid = perm_row[0]
        conn.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = :pid"),
            {'pid': pid}
        )
    conn.execute(
        sa.text("DELETE FROM permissions WHERE name = 'CLUB_MANAGE'")
    )
