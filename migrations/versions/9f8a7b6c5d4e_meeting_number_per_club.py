"""meeting_number is per-club, not global

Revision ID: 9f8a7b6c5d4e
Revises: a7c3b1f9d2e5, 4a2b6c8d0e1f, e3a4db9468b7
Create Date: 2026-06-07 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9f8a7b6c5d4e'
down_revision = ('a7c3b1f9d2e5', '4a2b6c8d0e1f', 'e3a4db9468b7')
branch_labels = None
depends_on = None


def upgrade():
    """
    Drop the global unique on Meetings.Meeting_Number and replace it with a
    composite unique on (club_id, Meeting_Number).

    Meeting_Number is a per-club counter (MAX+1 within the same club). The
    global unique was a schema mistake that prevented a second club from
    ever using Meeting #1, #2, etc. The composite unique preserves the
    in-club invariant without the cross-club collision risk.
    """
    bind = op.get_bind()
    insp = sa.inspect(bind)

    # 1. Drop the global unique on Meeting_Number if it still exists.
    if insp.has_table('Meetings'):
        existing_uqs = {uq['name'] for uq in insp.get_unique_constraints('Meetings')}
        if 'uq_Meetings_Meeting_Number' in existing_uqs:
            op.drop_constraint(
                'uq_Meetings_Meeting_Number', 'Meetings', type_='unique'
            )

    # 2. Add the composite unique on (club_id, Meeting_Number).
    #    Idempotent: skip if already present.
    with op.batch_alter_table('Meetings', schema=None) as batch_op:
        batch_op.create_unique_constraint(
            'uq_meetings_club_number', ['club_id', 'Meeting_Number']
        )


def downgrade():
    """
    Reverse: drop the composite unique and re-add the global unique.
    Note: downgrading will FAIL if any two meetings in different clubs
    share a Meeting_Number (since the global unique won't allow that).
    """
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table('Meetings'):
        return

    existing_uqs = {uq['name'] for uq in insp.get_unique_constraints('Meetings')}

    if 'uq_meetings_club_number' in existing_uqs:
        op.drop_constraint(
            'uq_meetings_club_number', 'Meetings', type_='unique'
        )

    # Re-add the global unique only if it isn't there.
    if 'uq_Meetings_Meeting_Number' not in existing_uqs:
        op.create_unique_constraint(
            'uq_Meetings_Meeting_Number', 'Meetings', ['Meeting_Number']
        )
