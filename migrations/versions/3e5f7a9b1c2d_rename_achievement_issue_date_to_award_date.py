"""rename achievement issue_date to award_date

Revision ID: 3e5f7a9b1c2d
Revises: 9a8b7c6d5e4f
Create Date: 2026-06-08 12:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3e5f7a9b1c2d'
down_revision = '9a8b7c6d5e4f'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy.engine.reflection import Inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    columns = [c['name'] for c in inspector.get_columns('achievements')]

    with op.batch_alter_table('achievements', schema=None) as batch_op:
        if 'issue_date' in columns and 'award_date' not in columns:
            batch_op.alter_column(
                'issue_date',
                new_column_name='award_date',
                existing_type=sa.Date(),
                existing_nullable=False,
            )


def downgrade():
    from sqlalchemy.engine.reflection import Inspector
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    columns = [c['name'] for c in inspector.get_columns('achievements')]

    with op.batch_alter_table('achievements', schema=None) as batch_op:
        if 'award_date' in columns and 'issue_date' not in columns:
            batch_op.alter_column(
                'award_date',
                new_column_name='issue_date',
                existing_type=sa.Date(),
                existing_nullable=False,
            )
