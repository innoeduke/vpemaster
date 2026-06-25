"""data_fix_null_auth_role_id_to_member

Revision ID: 3317b442785c
Revises: c2b3d4e5f6a8
Create Date: 2026-06-25 22:55:41.924015

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3317b442785c'
down_revision = 'c2b3d4e5f6a8'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    
    # 1. Get Member role ID
    role_id = connection.execute(
        sa.text("SELECT id FROM auth_roles WHERE name = 'Member'")
    ).scalar()
    
    # 2. Get sysadmin user ID
    sysadmin_id = connection.execute(
        sa.text("SELECT id FROM users WHERE username = 'sysadmin'")
    ).scalar()
    
    # 3. Update NULL roles to Member (except sysadmin)
    if role_id:
        if sysadmin_id:
            connection.execute(
                sa.text("""
                    UPDATE user_clubs 
                    SET auth_role_id = :role_id 
                    WHERE auth_role_id IS NULL AND user_id != :sysadmin_id
                """),
                {"role_id": role_id, "sysadmin_id": sysadmin_id}
            )
        else:
            connection.execute(
                sa.text("""
                    UPDATE user_clubs 
                    SET auth_role_id = :role_id 
                    WHERE auth_role_id IS NULL
                """),
                {"role_id": role_id}
            )


def downgrade():
    # Since we are backfilling missing data, downgrade does not need to revert this 
    # (setting roles back to NULL would degrade security/permissions).
    pass
