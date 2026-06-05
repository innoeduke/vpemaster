"""add agenda_view_unpublished permission

Revision ID: 02cfb8111fa4
Revises: b5d8fb847901
Create Date: 2026-05-14 12:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '02cfb8111fa4'
down_revision = 'b5d8fb847901'
branch_labels = None
depends_on = None


def upgrade():
    from datetime import datetime, timezone
    conn = op.get_bind()

    # 1. Add AGENDA_VIEW_UNPUBLISHED permission
    existing = conn.execute(
        sa.text("SELECT id FROM permissions WHERE name = 'AGENDA_VIEW_UNPUBLISHED'")
    ).fetchone()
    if not existing:
        conn.execute(
            sa.text("""
                INSERT INTO permissions (name, description, category, resource, action, created_at)
                VALUES ('AGENDA_VIEW_UNPUBLISHED',
                        'View unpublished meetings',
                        'agenda', 'agenda', 'view_unpublished', :created_at)
            """),
            {'created_at': datetime.now(timezone.utc)}
        )

    # 2. Grant to ClubAdmin, Operator, Staff, and User roles
    perm_row = conn.execute(
        sa.text("SELECT id FROM permissions WHERE name = 'AGENDA_VIEW_UNPUBLISHED'")
    ).fetchone()
    if not perm_row:
        return

    pid = perm_row[0]

    # Assign to all standard roles (not SysAdmin which has global override,
    # and not Guest which should NOT see unpublished by default)
    for role_name in ('ClubAdmin', 'Operator', 'Staff', 'Member'):
        role_row = conn.execute(
            sa.text("SELECT id FROM auth_roles WHERE name = :name"),
            {'name': role_name}
        ).fetchone()

        if role_row:
            rid = role_row[0]
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
    perm_row = conn.execute(
        sa.text("SELECT id FROM permissions WHERE name = 'AGENDA_VIEW_UNPUBLISHED'")
    ).fetchone()
    if perm_row:
        pid = perm_row[0]
        conn.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = :pid"),
            {'pid': pid}
        )
    conn.execute(
        sa.text("DELETE FROM permissions WHERE name = 'AGENDA_VIEW_UNPUBLISHED'")
    )
