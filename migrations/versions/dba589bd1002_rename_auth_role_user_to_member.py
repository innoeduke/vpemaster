"""rename auth_role User to Member

Revision ID: dba589bd1002
Revises: 8574707941e6
Create Date: 2026-06-05 13:13:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dba589bd1002'
down_revision = '8574707941e6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # Rename the base auth_role "User" to "Member" to match the canonical
    # name used throughout the application code. Only affects rows whose
    # name is exactly 'User' — ClubAdmin/Operator/Staff/SysAdmin/Guest
    # are untouched. The (club_id, name) unique constraint is preserved
    # because we are renaming in place, not inserting a new row.
    result = conn.execute(
        sa.text("UPDATE auth_roles SET name = 'Member' WHERE name = 'User'")
    )
    print(f"[rename_user_role_to_member] Updated {result.rowcount} auth_role row(s) from 'User' to 'Member'.")


def downgrade():
    conn = op.get_bind()

    # Revert the rename. Safe to run only if no 'User' row was created
    # independently after the upgrade ran.
    result = conn.execute(
        sa.text("UPDATE auth_roles SET name = 'User' WHERE name = 'Member'")
    )
    print(f"[rename_user_role_to_member] Reverted {result.rowcount} auth_role row(s) from 'Member' to 'User'.")
