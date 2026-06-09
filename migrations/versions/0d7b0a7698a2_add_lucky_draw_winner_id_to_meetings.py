"""add lucky_draw_winner_id to Meetings

Revision ID: 0d7b0a7698a2
Revises: 3e5f7a9b1c2d
Create Date: 2026-06-09 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0d7b0a7698a2'
down_revision = '3e5f7a9b1c2d'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('Meetings', sa.Column('lucky_draw_winner_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_meetings_lucky_draw_winner_id', 'Meetings', 'Contacts',
        ['lucky_draw_winner_id'], ['id']
    )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    fks = inspector.get_foreign_keys('Meetings')
    for fk in fks:
        if 'lucky_draw_winner_id' in fk.get('constrained_columns', []):
            op.drop_constraint(fk['name'], 'Meetings', type_='foreignkey')

    columns = [col['name'] for col in inspector.get_columns('Meetings')]
    if 'lucky_draw_winner_id' in columns:
        op.drop_column('Meetings', 'lucky_draw_winner_id')
