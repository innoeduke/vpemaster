"""add club_id to role_permissions and backfill per-club

Makes the permissions matrix per-club: each (role, permission) pair is now
scoped to a specific club via club_id, so different clubs can hold different
matrices for the same role.

Backfill strategy: the matrix was previously global (81 rows, no club scope).
To preserve the current effective matrix for every active club:

  1. Add club_id (nullable) to role_permissions.
  2. Drop the old (role_id, permission_id) unique constraint (the new world
     has 4 rows per pair, one per active club).
  3. Assign the original 81 rows to SHLTMC (club_no='00868941', the source
     of truth for the current matrix).
  4. INSERT copies of those 81 rows for every OTHER active club
     (status='active', club_no != '000001').
  5. Enforce club_id NOT NULL and add the new
     (role_id, permission_id, club_id) unique constraint.

The global fallback JSON (app/static/permissions_default.json) is the
ultimate Reset-to-Default target; it ships in this same commit and is
populated from the same 66 valid role->[permission] mappings that the
SHLTMC backfill carries (the 15 orphan FKs to deleted permissions are
intentionally excluded from the JSON -- they have no name to export).

Revision ID: a1b2c3d4e5f7
Revises: 4b5c6d7e8f90
Create Date: 2026-06-05 19:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f7'
down_revision = '4b5c6d7e8f90'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # 1. Add club_id as nullable (we backfill before enforcing NOT NULL).
    with op.batch_alter_table('role_permissions') as batch_op:
        batch_op.add_column(sa.Column('club_id', sa.Integer(), nullable=True))
        batch_op.create_index('ix_role_permissions_club_id', ['club_id'])

    # 2. Add a non-unique index on role_id BEFORE dropping the old unique,
    #    so the FK role_permissions.role_id -> auth_roles.id still has a
    #    backing index. (MySQL refuses to drop an index that is the only
    #    one backing an FK.) The new unique we'll add in step 6 starts with
    #    role_id too, so this helper becomes redundant after step 6; we
    #    drop it there to avoid a duplicate-prefix index.
    with op.batch_alter_table('role_permissions') as batch_op:
        batch_op.create_index('ix_role_permissions_role_id', ['role_id'])
        batch_op.drop_constraint('unique_role_permission', type_='unique')

    # 3 + 4. Backfill: assign the 81 existing rows to SHLTMC, then copy
    #         them to every other active club (excluding the super club).
    #         First, drop any orphan rows whose permission_id no longer
    #         exists in the permissions table -- the FK to permissions is
    #         enforced for new inserts, so we can't re-insert these when
    #         copying to the other clubs. These rows are meaningless (no
    #         permission name to resolve), so removing them is a clean fix.
    op.execute(
        sa.text(
            "DELETE FROM role_permissions "
            "WHERE permission_id NOT IN (SELECT id FROM permissions)"
        )
    )

    shltmc_id = bind.execute(
        sa.text("SELECT id FROM clubs WHERE club_no = '00868941'")
    ).scalar()

    if shltmc_id is not None:
        bind.execute(
            sa.text("UPDATE role_permissions SET club_id = :cid"),
            {"cid": shltmc_id},
        )

        other_active_ids = [row[0] for row in bind.execute(sa.text(
            "SELECT id FROM clubs "
            "WHERE status = 'active' AND club_no != '000001' AND id != :shltmc"
        ), {"shltmc": shltmc_id}).fetchall()]

        for other_id in other_active_ids:
            bind.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id, club_id) "
                    "SELECT role_id, permission_id, :cid "
                    "FROM role_permissions WHERE club_id = :src"
                ),
                {"cid": other_id, "src": shltmc_id},
            )

    # 5. Enforce NOT NULL and add the per-club unique constraint.
    with op.batch_alter_table('role_permissions') as batch_op:
        batch_op.alter_column('club_id', existing_type=sa.Integer(), nullable=False)
        batch_op.create_unique_constraint(
            'unique_role_permission_club',
            ['role_id', 'permission_id', 'club_id'],
        )
        # Drop the helper role_id index now that the new unique (which
        # starts with role_id) backs the role_id FK.
        batch_op.drop_index('ix_role_permissions_role_id')


def downgrade():
    # Best-effort downgrade: relax to the old global shape. The per-club
    # rows (the duplicates created in step 4) are NOT removed here; if you
    # genuinely need to roll back, prune rows where club_id != SHLTMC first.
    with op.batch_alter_table('role_permissions') as batch_op:
        batch_op.drop_constraint('unique_role_permission_club', type_='unique')
        batch_op.alter_column('club_id', existing_type=sa.Integer(), nullable=True)
        batch_op.create_unique_constraint(
            'unique_role_permission', ['role_id', 'permission_id']
        )
        batch_op.drop_index('ix_role_permissions_club_id')
        batch_op.drop_column('club_id')
