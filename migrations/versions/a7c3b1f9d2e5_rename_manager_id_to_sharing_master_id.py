"""rename meeting manager_id to sharing_master_id and backfill

Revision ID: a7c3b1f9d2e5
Revises: 3d5e8695df3c
Create Date: 2026-06-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7c3b1f9d2e5'
down_revision = '3d5e8695df3c'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('Meetings')]

    # 1. Rename manager_id -> sharing_master_id (idempotent)
    if 'manager_id' in columns and 'sharing_master_id' not in columns:
        with op.batch_alter_table('Meetings', schema=None) as batch_op:
            batch_op.alter_column(
                'manager_id',
                new_column_name='sharing_master_id',
                existing_type=sa.Integer(),
                nullable=True,
            )

    # 2. Backfill sharing_master_id using raw SQL only.
    # Mirrors Meeting.update_sharing_master(): for each meeting, pick the first
    # featured Session_Log (lowest Meeting_Seq, then lowest id), then take the
    # first owner from owner_meeting_roles matching that log's role context.
    # We avoid the ORM model here because later migrations add columns to
    # Meetings (lucky_draw_winner_id, best_debater_id) — using Meeting.query
    # would generate a SELECT referencing columns that don't exist yet on a
    # fresh DB upgrading through this revision.
    featured_rows = conn.execute(sa.text("""
        SELECT
            sl.meeting_id AS meeting_id,
            sl.id AS sl_id,
            st.role_id AS role_id,
            COALESCE(mr.has_single_owner, 1) AS has_single_owner
        FROM Session_Logs sl
        JOIN Session_Types st ON sl.Type_ID = st.id
        LEFT JOIN meeting_roles mr ON mr.id = st.role_id
        WHERE st.Featured = 1 AND sl.meeting_id IS NOT NULL
        ORDER BY sl.meeting_id ASC,
                 COALESCE(sl.Meeting_Seq, 0) ASC,
                 sl.id ASC
    """)).fetchall()

    # First featured session_log per meeting
    first_per_meeting = {}
    for row in featured_rows:
        meeting_id = row[0]
        if meeting_id not in first_per_meeting:
            first_per_meeting[meeting_id] = row

    # Reset sharing_master_id to NULL — the column was just renamed from
    # manager_id and the semantics have changed, so old values must not leak
    # through for meetings without a featured-session owner.
    conn.execute(sa.text("UPDATE Meetings SET sharing_master_id = NULL"))

    # Populate sharing_master_id for meetings whose first featured session has owners.
    for meeting_id, row in first_per_meeting.items():
        sl_id = row[1]
        role_id = row[2]
        has_single_owner = bool(row[3])

        params = {
            'meeting_id': meeting_id,
            'role_id': role_id,
        }
        if has_single_owner:
            params['sl_id'] = sl_id
            owner_sql = sa.text("""
                SELECT contact_id
                FROM owner_meeting_roles
                WHERE meeting_id = :meeting_id
                  AND role_id <=> :role_id
                  AND session_log_id = :sl_id
                ORDER BY id ASC
                LIMIT 1
            """)
        else:
            owner_sql = sa.text("""
                SELECT contact_id
                FROM owner_meeting_roles
                WHERE meeting_id = :meeting_id
                  AND role_id <=> :role_id
                ORDER BY id ASC
                LIMIT 1
            """)

        owner_row = conn.execute(owner_sql, params).first()
        if owner_row and owner_row[0] is not None:
            conn.execute(
                sa.text("UPDATE Meetings SET sharing_master_id = :cid WHERE id = :mid"),
                {'cid': owner_row[0], 'mid': meeting_id},
            )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('Meetings')]

    if 'sharing_master_id' in columns and 'manager_id' not in columns:
        with op.batch_alter_table('Meetings', schema=None) as batch_op:
            batch_op.alter_column(
                'sharing_master_id',
                new_column_name='manager_id',
                existing_type=sa.Integer(),
                nullable=True,
            )
