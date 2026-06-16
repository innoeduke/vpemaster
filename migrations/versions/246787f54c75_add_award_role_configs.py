"""Add award_role_configs associative table

Revision ID: 246787f54c75
Revises: 519065b594b4
Create Date: 2026-06-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '246787f54c75'
down_revision = '519065b594b4'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create the associative table
    op.create_table(
        'award_role_configs',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('award_config_id', sa.Integer,
                  sa.ForeignKey('meeting_award_configs.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('meeting_role_id', sa.Integer,
                  sa.ForeignKey('meeting_roles.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.UniqueConstraint('award_config_id', 'meeting_role_id', name='uq_award_role_config'),
    )

    # 2. Backfill: for every MeetingAwardConfig with associated_role set,
    #    find the matching MeetingRole by name within the same club or global
    #    and create an AwardRoleConfig row.
    bind = op.get_bind()
    from sqlalchemy import text
    rows = bind.execute(text("""
        SELECT mac.id AS config_id, mac.associated_role, m.club_id
        FROM meeting_award_configs mac
        JOIN Meetings m ON m.id = mac.meeting_id
        WHERE mac.associated_role IS NOT NULL
    """)).fetchall()
    for config_id, role_name, club_id in rows:
        mr = bind.execute(text("""
            SELECT id FROM meeting_roles
            WHERE name = :name AND (club_id = :club_id OR club_id = :global)
            ORDER BY (club_id = :club_id) DESC
            LIMIT 1
        """), {"name": role_name, "club_id": club_id, "global": 1}).first()
        if not mr:
            continue
        exists = bind.execute(text("""
            SELECT 1 FROM award_role_configs
            WHERE award_config_id = :cid AND meeting_role_id = :rid
        """), {"cid": config_id, "rid": mr[0]}).first()
        if exists:
            continue
        bind.execute(text("""
            INSERT INTO award_role_configs (award_config_id, meeting_role_id)
            VALUES (:cid, :rid)
        """), {"cid": config_id, "rid": mr[0]})


def downgrade():
    op.drop_table('award_role_configs')
