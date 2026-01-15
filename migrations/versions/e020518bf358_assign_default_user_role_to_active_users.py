"""assign_default_user_role_to_active_users

Revision ID: e020518bf358
Revises: 668a0a909903
Create Date: 2026-01-16 03:17:11.198661

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column, select
from datetime import datetime, timezone


# revision identifiers, used by Alembic.
revision = 'e020518bf358'
down_revision = '668a0a909903'
branch_labels = None
depends_on = None


def upgrade():
    """Assign the 'User' role to all active users who don't have any role assigned."""
    
    # Create table references for the query
    users_table = table('Users',
        column('id', sa.Integer),
        column('Status', sa.String)
    )
    
    auth_roles_table = table('auth_roles',
        column('id', sa.Integer),
        column('name', sa.String)
    )
    
    user_roles_table = table('user_roles',
        column('id', sa.Integer),
        column('user_id', sa.Integer),
        column('role_id', sa.Integer),
        column('assigned_at', sa.DateTime),
        column('assigned_by', sa.Integer)
    )
    
    # Get database connection
    conn = op.get_bind()
    
    # Find the 'User' role ID
    user_role_result = conn.execute(
        select(auth_roles_table.c.id).where(auth_roles_table.c.name == 'User')
    ).fetchone()
    
    if not user_role_result:
        print("Warning: 'User' role not found in auth_roles table. Skipping migration.")
        return
    
    user_role_id = user_role_result[0]
    
    # Find all active users
    active_users = conn.execute(
        select(users_table.c.id).where(users_table.c.Status == 'active')
    ).fetchall()
    
    if not active_users:
        print("No active users found. Skipping migration.")
        return
    
    active_user_ids = [user[0] for user in active_users]
    
    # Find users who already have roles assigned
    users_with_roles = conn.execute(
        select(user_roles_table.c.user_id).where(
            user_roles_table.c.user_id.in_(active_user_ids)
        ).distinct()
    ).fetchall()
    
    users_with_role_ids = {user[0] for user in users_with_roles}
    
    # Find users without any roles
    users_without_roles = [uid for uid in active_user_ids if uid not in users_with_role_ids]
    
    if not users_without_roles:
        print("All active users already have roles assigned. Skipping migration.")
        return
    
    # Assign 'User' role to users without roles
    current_time = datetime.now(timezone.utc)
    
    for user_id in users_without_roles:
        conn.execute(
            user_roles_table.insert().values(
                user_id=user_id,
                role_id=user_role_id,
                assigned_at=current_time,
                assigned_by=None  # System-assigned, no specific user
            )
        )
    
    print(f"Assigned 'User' role to {len(users_without_roles)} active user(s) without roles.")


def downgrade():
    """
    Downgrade is intentionally left empty.
    
    We don't remove the assigned roles during downgrade because:
    1. It's safer to leave users with roles than to remove them
    2. The roles were assigned based on business logic (active users should have roles)
    3. Removing roles could break access control
    """
    pass

