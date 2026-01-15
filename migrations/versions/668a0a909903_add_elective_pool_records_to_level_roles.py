"""add elective pool records to level_roles

Revision ID: 668a0a909903
Revises: c6c74fed835c
Create Date: 2026-01-16 02:07:38.026895

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '668a0a909903'
down_revision = 'c6c74fed835c'
branch_labels = None
depends_on = None


def upgrade():
    # Insert records for Elective Pool for each level
    level_roles_table = sa.table('level_roles',
        sa.column('level', sa.Integer),
        sa.column('role', sa.String),
        sa.column('type', sa.String),
        sa.column('count_required', sa.Integer)
    )
    
    op.bulk_insert(level_roles_table, [
        {'level': 1, 'role': 'Elective Pool', 'type': 'elective', 'count_required': 1},
        {'level': 2, 'role': 'Elective Pool', 'type': 'elective', 'count_required': 1},
        {'level': 3, 'role': 'Elective Pool', 'type': 'elective', 'count_required': 1},
        {'level': 4, 'role': 'Elective Pool', 'type': 'elective', 'count_required': 2},
        {'level': 5, 'role': 'Elective Pool', 'type': 'elective', 'count_required': 2},
    ])


def downgrade():
    op.execute("DELETE FROM level_roles WHERE role = 'Elective Pool'")
