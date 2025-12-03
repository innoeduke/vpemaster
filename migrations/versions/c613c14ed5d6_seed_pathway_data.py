"""seed pathway data

Revision ID: c613c14ed5d6
Revises: 5a6502921e8a
Create Date: 2025-12-03 23:48:39.175859

"""
from alembic import op
import sqlalchemy as sa
import csv
import os

# revision identifiers, used by Alembic.
revision = 'c613c14ed5d6'
down_revision = '4c34ee4b927d'
branch_labels = None
depends_on = None


def upgrade():
    pathways_table = sa.table(
        'pathways',
        sa.column('name', sa.String),
        sa.column('abbr', sa.String),
        sa.column('type', sa.String)
    )

    pathways_data = [
        {'name': 'Dynamic Leadership', 'abbr': 'DL', 'type': 'pathway'},
        {'name': 'Engaging Humor', 'abbr': 'EH', 'type': 'pathway'},
        {'name': 'Motivational Strategies', 'abbr': 'MS', 'type': 'pathway'},
        {'name': 'Persuasive Influence', 'abbr': 'PI', 'type': 'pathway'},
        {'name': 'Presentation Mastery', 'abbr': 'PM', 'type': 'pathway'},
        {'name': 'Visionary Communication', 'abbr': 'VC', 'type': 'pathway'},
        {'name': 'Distinguished Toastmasters', 'abbr': 'DTM', 'type': 'program'},
        {'name': 'Generic', 'abbr': 'TM', 'type': 'dummy'},
        {'name': 'Successful Club Series', 'abbr': 'SC', 'type': 'presentation'},
        {'name': 'Better Speaker Series', 'abbr': 'BS', 'type': 'presentation'},
        {'name': 'Leadership Excellence Series',
            'abbr': 'LE', 'type': 'presentation'},
    ]

    op.bulk_insert(pathways_table, pathways_data)


def downgrade():
    op.execute('DELETE FROM pathways')
