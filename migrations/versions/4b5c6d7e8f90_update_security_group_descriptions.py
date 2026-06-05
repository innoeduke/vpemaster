"""update security group descriptions

Revision ID: 4b5c6d7e8f90
Revises: 3aa72be48b62
Create Date: 2026-06-05 19:24:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4b5c6d7e8f90'
down_revision = '3aa72be48b62'
branch_labels = None
depends_on = None


# Original descriptions captured from production snapshot
# (instance/backup/db/backup_db_full_20260528_004531.sql).
# Used by downgrade() to restore the previous values verbatim.
ORIGINAL_DESCRIPTIONS = {
    'SysAdmin':  'Admin role',
    'ClubAdmin': 'VPE role',
    'Operator':  'Operator role',
    'Staff':     'Officer role',
    'Member':    'Member role',
    'Guest':     None,  # was NULL
}


def upgrade():
    conn = op.get_bind()

    # ClubAdmin — "VPE role" undersells the scope; this group owns full club
    # config (members, security groups, modules, speech logs, all-data edit).
    r = conn.execute(
        sa.text(
            "UPDATE auth_roles SET description = "
            "'Club leadership team — full configuration of this club: members, security groups, modules, speech logs, and all data. "
            "Typically held by the VPE or President.' "
            "WHERE name = 'ClubAdmin' AND club_id IS NULL"
        )
    )
    print(f"[update_security_group_descriptions] ClubAdmin: {r.rowcount} row(s) updated.")

    # Operator — meeting operations lead (SAA, meeting chairs).
    r = conn.execute(
        sa.text(
            "UPDATE auth_roles SET description = "
            "'Meeting operations lead — owns the weekly meeting: agenda, roster, booking, lucky draw, voting results, and speech-log tracking. "
            "Typically held by the SAA and meeting chairs.' "
            "WHERE name = 'Operator' AND club_id IS NULL"
        )
    )
    print(f"[update_security_group_descriptions] Operator: {r.rowcount} row(s) updated.")

    # Staff — club officer with view-all + planner + own-profile editing.
    r = conn.execute(
        sa.text(
            "UPDATE auth_roles SET description = "
            "'Club officer — view access across all club data plus the planner and own-profile editing. "
            "Held by the seven club officers.' "
            "WHERE name = 'Staff' AND club_id IS NULL"
        )
    )
    print(f"[update_security_group_descriptions] Staff: {r.rowcount} row(s) updated.")

    # Member — key off the post-rename name (see dba589bd1002).
    r = conn.execute(
        sa.text(
            "UPDATE auth_roles SET description = "
            "'Club member — view published club content, book own meeting roles, edit own profile, and track own speech-log progress.' "
            "WHERE name = 'Member' AND club_id IS NULL"
        )
    )
    print(f"[update_security_group_descriptions] Member: {r.rowcount} row(s) updated.")

    # Guest — anonymous visitor, public pages only.
    r = conn.execute(
        sa.text(
            "UPDATE auth_roles SET description = "
            "'Anonymous visitor — view the public club home page, agenda, and Pathway library. No login required.' "
            "WHERE name = 'Guest' AND club_id IS NULL"
        )
    )
    print(f"[update_security_group_descriptions] Guest: {r.rowcount} row(s) updated.")

    # SysAdmin — hidden from the club matrix but still a system role;
    # keep the description in sync so the audit log / future tooling reads it.
    r = conn.execute(
        sa.text(
            "UPDATE auth_roles SET description = "
            "'System administrator — unrestricted access across all clubs, settings, modules, and data. "
            "Hidden from the club-level permissions matrix by design.' "
            "WHERE name = 'SysAdmin' AND club_id IS NULL"
        )
    )
    print(f"[update_security_group_descriptions] SysAdmin: {r.rowcount} row(s) updated.")


def downgrade():
    conn = op.get_bind()

    # Restore original descriptions. Each statement is safe to re-run
    # because it targets the original value (or NULL for Guest) and
    # the (club_id IS NULL) filter.
    for name, original in ORIGINAL_DESCRIPTIONS.items():
        if original is None:
            r = conn.execute(
                sa.text(
                    "UPDATE auth_roles SET description = NULL "
                    "WHERE name = :name AND club_id IS NULL"
                ),
                {"name": name},
            )
        else:
            r = conn.execute(
                sa.text(
                    "UPDATE auth_roles SET description = :desc "
                    "WHERE name = :name AND club_id IS NULL"
                ),
                {"name": name, "desc": original},
            )
        print(f"[update_security_group_descriptions] {name}: {r.rowcount} row(s) reverted.")
