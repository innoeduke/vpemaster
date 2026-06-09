"""Add self check-in fields to roster

Revision ID: 93e0d3a1c6e0
Revises: 0d7b0a7698a2
Create Date: 2026-06-10 03:08:56.891540

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


# revision identifiers, used by Alembic.
revision = '93e0d3a1c6e0'
down_revision = '0d7b0a7698a2'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('roster', schema=None) as batch_op:
        batch_op.add_column(sa.Column('checked_in_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('checked_in_via', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('checked_in_by_user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f('fk_roster_checked_in_by_user_id_users'),
            'users', ['checked_in_by_user_id'], ['id']
        )

    # Backfill: insert a disabled ClubModule row for every existing club so
    # the new 'Self Check-In' toggle appears in settings without being on by
    # default. The uq_club_module unique constraint makes this idempotent.
    bind = op.get_bind()
    clubs_t = table('clubs', column('id', sa.Integer))
    cm_t = table(
        'club_modules',
        column('club_id', sa.Integer),
        column('module_name', sa.String),
        column('is_enabled', sa.Boolean),
    )
    club_ids = [row[0] for row in bind.execute(sa.select(clubs_t.c.id)).fetchall()]
    if club_ids:
        existing = bind.execute(
            sa.select(cm_t.c.club_id).where(
                sa.and_(
                    cm_t.c.module_name == 'Self Check-In',
                    cm_t.c.club_id.in_(club_ids),
                )
            )
        ).fetchall()
        already = {row[0] for row in existing}
        to_insert = [
            {'club_id': cid, 'module_name': 'Self Check-In', 'is_enabled': False}
            for cid in club_ids if cid not in already
        ]
        if to_insert:
            op.bulk_insert(cm_t, to_insert)


def downgrade():
    bind = op.get_bind()
    cm_t = table(
        'club_modules',
        column('club_id', sa.Integer),
        column('module_name', sa.String),
    )
    bind.execute(sa.delete(cm_t).where(cm_t.c.module_name == 'Self Check-In'))

    with op.batch_alter_table('roster', schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f('fk_roster_checked_in_by_user_id_users'), type_='foreignkey'
        )
        batch_op.drop_column('checked_in_by_user_id')
        batch_op.drop_column('checked_in_via')
        batch_op.drop_column('checked_in_at')
