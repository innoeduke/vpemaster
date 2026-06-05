"""consolidate booking and profile own permissions

Revision ID: 3aa72be48b62
Revises: f72f66fd02cf
Create Date: 2026-06-05 18:33:49.370507

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3aa72be48b62'
down_revision = 'f72f66fd02cf'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    from datetime import datetime, timezone
    created_at = datetime.now(timezone.utc)
    
    # 1. Insert MEMBERS_SELF permission if not exists
    perm_exists = conn.execute(
        sa.text("SELECT id FROM permissions WHERE name = :name"),
        {"name": "MEMBERS_SELF"}
    ).fetchone()
    
    if not perm_exists:
        conn.execute(
            sa.text(
                "INSERT INTO permissions (name, description, category, resource, action, created_at) "
                "VALUES (:name, :desc, :cat, :res, :act, :created_at)"
            ),
            {
                "name": "MEMBERS_SELF",
                "desc": "Manage own profile, password, and bookings",
                "cat": "members",
                "res": "members",
                "act": "manage_own",
                "created_at": created_at
            }
        )
        # Fetch the newly inserted permission ID
        members_self_id = conn.execute(
            sa.text("SELECT id FROM permissions WHERE name = :name"),
            {"name": "MEMBERS_SELF"}
        ).scalar()
    else:
        members_self_id = perm_exists[0]
        
    # 2. Get IDs of BOOKING_OWN and PROFILE_OWN
    booking_own_res = conn.execute(
        sa.text("SELECT id FROM permissions WHERE name = :name"),
        {"name": "BOOKING_OWN"}
    ).fetchone()
    booking_own_id = booking_own_res[0] if booking_own_res else None
    
    profile_own_res = conn.execute(
        sa.text("SELECT id FROM permissions WHERE name = :name"),
        {"name": "PROFILE_OWN"}
    ).fetchone()
    profile_own_id = profile_own_res[0] if profile_own_res else None
    
    # 3. Find all roles associated with BOOKING_OWN or PROFILE_OWN
    old_perm_ids = [pid for pid in (booking_own_id, profile_own_id) if pid is not None]
    if old_perm_ids:
        # Construct query parameters dynamically to avoid issues
        role_ids = set()
        for old_pid in old_perm_ids:
            rows = conn.execute(
                sa.text("SELECT role_id FROM role_permissions WHERE permission_id = :old_pid"),
                {"old_pid": old_pid}
            ).fetchall()
            for r in rows:
                role_ids.add(r[0])
                
        # 4. Associate those roles with MEMBERS_SELF
        for role_id in role_ids:
            # Check if association already exists
            assoc_exists = conn.execute(
                sa.text("SELECT id FROM role_permissions WHERE role_id = :role_id AND permission_id = :perm_id"),
                {"role_id": role_id, "perm_id": members_self_id}
            ).fetchone()
            if not assoc_exists:
                conn.execute(
                    sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :perm_id)"),
                    {"role_id": role_id, "perm_id": members_self_id}
                )
                
        # 5. Delete role associations for BOOKING_OWN and PROFILE_OWN
        for old_pid in old_perm_ids:
            conn.execute(
                sa.text("DELETE FROM role_permissions WHERE permission_id = :old_pid"),
                {"old_pid": old_pid}
            )
            
    # 6. Delete BOOKING_OWN and PROFILE_OWN from permissions table
    conn.execute(
        sa.text("DELETE FROM permissions WHERE name IN ('BOOKING_OWN', 'PROFILE_OWN')")
    )


def downgrade():
    conn = op.get_bind()
    from datetime import datetime, timezone
    created_at = datetime.now(timezone.utc)
    
    # 1. Insert BOOKING_OWN and PROFILE_OWN back if they do not exist
    old_perms = [
        ("BOOKING_OWN", "Book or cancel own meeting roles, and view own speech/project log history", "meeting", "booking", "own"),
        ("PROFILE_OWN", "View and edit own profile", "profile", "profile", "view_own")
    ]
    
    old_perm_ids = {}
    for name, desc, cat, res, act in old_perms:
        exists = conn.execute(
            sa.text("SELECT id FROM permissions WHERE name = :name"),
            {"name": name}
        ).fetchone()
        if not exists:
            conn.execute(
                sa.text(
                    "INSERT INTO permissions (name, description, category, resource, action, created_at) "
                    "VALUES (:name, :desc, :cat, :res, :act, :created_at)"
                ),
                {
                    "name": name,
                    "desc": desc,
                    "cat": cat,
                    "res": res,
                    "act": act,
                    "created_at": created_at
                }
            )
            pid = conn.execute(
                sa.text("SELECT id FROM permissions WHERE name = :name"),
                {"name": name}
            ).scalar()
        else:
            pid = exists[0]
        old_perm_ids[name] = pid
        
    # 2. Get MEMBERS_SELF ID
    members_self_res = conn.execute(
        sa.text("SELECT id FROM permissions WHERE name = :name"),
        {"name": "MEMBERS_SELF"}
    ).fetchone()
    members_self_id = members_self_res[0] if members_self_res else None
    
    if members_self_id:
        # 3. Find all roles associated with MEMBERS_SELF
        rows = conn.execute(
            sa.text("SELECT role_id FROM role_permissions WHERE permission_id = :members_self_id"),
            {"members_self_id": members_self_id}
        ).fetchall()
        
        # 4. Associate those roles with BOOKING_OWN and PROFILE_OWN
        for r in rows:
            role_id = r[0]
            for old_name, old_pid in old_perm_ids.items():
                assoc_exists = conn.execute(
                    sa.text("SELECT id FROM role_permissions WHERE role_id = :role_id AND permission_id = :old_pid"),
                    {"role_id": role_id, "old_pid": old_pid}
                ).fetchone()
                if not assoc_exists:
                    conn.execute(
                        sa.text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :old_pid)"),
                        {"role_id": role_id, "old_pid": old_pid}
                    )
                    
        # 5. Delete role associations for MEMBERS_SELF
        conn.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = :members_self_id"),
            {"members_self_id": members_self_id}
        )
        
        # 6. Delete MEMBERS_SELF from permissions table
        conn.execute(
            sa.text("DELETE FROM permissions WHERE id = :members_self_id"),
            {"members_self_id": members_self_id}
        )
