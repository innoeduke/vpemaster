"""add operator auth role with level 3

Revision ID: b4f7a2c1d839
Revises: a1b2c3d4e5f6
Create Date: 2026-04-07 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b4f7a2c1d839'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    from datetime import datetime, timezone
    conn = op.get_bind()
    
    # 1. Add Operator role with level 3 (between Staff=2 and ClubAdmin=4)
    existing = conn.execute(sa.text("SELECT id FROM auth_roles WHERE name = 'Operator'")).fetchone()
    if not existing:
        conn.execute(
            sa.text("""
                INSERT INTO auth_roles (name, description, level, created_at) 
                VALUES ('Operator', 'Operator role for managing meetings and bookings', 3, :created_at)
            """),
            {'created_at': datetime.now(timezone.utc)}
        )
    
    # 2. Copy Staff permissions to Operator as a baseline
    operator_role = conn.execute(sa.text("SELECT id FROM auth_roles WHERE name = 'Operator'")).fetchone()
    staff_role = conn.execute(sa.text("SELECT id FROM auth_roles WHERE name = 'Staff'")).fetchone()
    
    if operator_role and staff_role:
        oid = operator_role[0]
        sid = staff_role[0]
        
        # Get all Staff permissions
        staff_perms = conn.execute(
            sa.text("SELECT permission_id FROM role_permissions WHERE role_id = :sid"),
            {'sid': sid}
        ).fetchall()
        
        for (pid,) in staff_perms:
            # Check if assignment already exists
            exists = conn.execute(
                sa.text("SELECT 1 FROM role_permissions WHERE role_id = :oid AND permission_id = :pid"),
                {'oid': oid, 'pid': pid}
            ).fetchone()
            
            if not exists:
                conn.execute(
                    sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:oid, :pid)"),
                    {'oid': oid, 'pid': pid}
                )


def downgrade():
    conn = op.get_bind()
    
    # Remove all role_permissions for Operator first
    operator_role = conn.execute(sa.text("SELECT id FROM auth_roles WHERE name = 'Operator'")).fetchone()
    if operator_role:
        oid = operator_role[0]
        conn.execute(sa.text("DELETE FROM role_permissions WHERE role_id = :oid"), {'oid': oid})
    
    # Remove the Operator role
    conn.execute(sa.text("DELETE FROM auth_roles WHERE name = 'Operator'"))
