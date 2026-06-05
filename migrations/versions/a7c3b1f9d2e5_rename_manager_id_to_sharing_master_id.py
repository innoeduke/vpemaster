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

    # 2. Backfill: for every meeting, set sharing_master_id to the contact id
    # of the first owner of the first Featured Session (via Meeting.update_sharing_master).
    from app import create_app
    from app.models.base import db
    from app.models.meeting import Meeting

    app = create_app()
    with app.app_context():
        for meeting in Meeting.query.all():
            meeting.update_sharing_master()
        db.session.commit()


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
