"""grant agenda and pathway view permissions to guest role

Revision ID: 26a80f67f9e7
Revises: b2ec9631b851
Create Date: 2026-01-17 01:49:27.344628

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '26a80f67f9e7'
down_revision = 'b2ec9631b851'
branch_labels = None
depends_on = None


def upgrade():
    # Force auto-commit since we're doing data manipulation
    conn = op.get_bind()
    
    # 1. Fetch Guest Role ID
    guest_role = conn.execute(sa.text("SELECT id FROM auth_roles WHERE name = 'Guest'")).fetchone()
    if not guest_role:
        print("Guest role not found, skipping permission assignment.")
        return
    guest_role_id = guest_role[0]
    
    # 2. Fetch Permission IDs
    perms_to_assign = ['AGENDA_VIEW', 'PATHWAY_LIB_VIEW']
    for perm_name in perms_to_assign:
        perm = conn.execute(sa.text("SELECT id FROM permissions WHERE name = :name"), {'name': perm_name}).fetchone()
        if perm:
            perm_id = perm[0]
            # Check if assignment already exists
            exists = conn.execute(
                sa.text("SELECT 1 FROM role_permissions WHERE role_id = :rid AND permission_id = :pid"),
                {'rid': guest_role_id, 'pid': perm_id}
            ).fetchone()
            
            if not exists:
                conn.execute(
                    sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:rid, :pid)"),
                    {'rid': guest_role_id, 'pid': perm_id}
                )
                print(f"Assigned {perm_name} to Guest role.")
        else:
            print(f"Permission {perm_name} not found in database.")


def downgrade():
    conn = op.get_bind()
    guest_role = conn.execute(sa.text("SELECT id FROM auth_roles WHERE name = 'Guest'")).fetchone()
    if guest_role:
        role_id = guest_role[0]
        conn.execute(
            sa.text("""
                DELETE FROM role_permissions 
                WHERE role_id = :rid 
                AND permission_id IN (SELECT id FROM permissions WHERE name IN ('AGENDA_VIEW', 'PATHWAY_LIB_VIEW'))
            """),
            {'rid': role_id}
        )
