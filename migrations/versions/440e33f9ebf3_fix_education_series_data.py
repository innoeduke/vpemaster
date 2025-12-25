"""fix_education_series_data

Revision ID: 440e33f9ebf3
Revises: 5a6502921e8a
Create Date: 2025-12-25 18:44:56.978467

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '440e33f9ebf3'
down_revision = '5a6502921e8a'
branch_labels = None
depends_on = None



from sqlalchemy.sql import table, column
from sqlalchemy import String, Integer, SmallInteger

def upgrade():
    # 1. Clean up Presentation series (strip \r and whitespace)
    # Using specific SQL dialect syntax or generic if possible. For MySQL:
    op.execute("UPDATE presentations SET series = TRIM(REPLACE(series, '\r', '')) WHERE series IS NOT NULL")

    # 2. Correct Topicsmaster spelling in Roles
    op.execute("UPDATE roles SET name = 'Topicsmaster' WHERE name = 'Topicmaster'")

    # 3. Ensure LevelRole presentation requirements
    # Define table interface
    level_roles = table('level_roles',
        column('level', SmallInteger),
        column('role', String),
        column('type', String),
        column('count_required', Integer)
    )

    requirements = [
        {'level': 3, 'role': 'Successful Club Series', 'type': 'required', 'count_required': 1},
        {'level': 4, 'role': 'Successful Club Series', 'type': 'required', 'count_required': 1},
        {'level': 4, 'role': 'Better Speaker Series', 'type': 'required', 'count_required': 1},
        {'level': 5, 'role': 'Successful Club Series', 'type': 'required', 'count_required': 1},
        {'level': 5, 'role': 'Leadership Excellence Series', 'type': 'required', 'count_required': 1},
    ]

    # For each requirement, we want to ensure it exists.
    # Alembic doesn't have a simple "upsert" across all DBs.
    # We can use a custom DELETE then INSERT strategy or a conditional INSERT.
    # Since this is a specific data fix, checking existence via SQL is safest.
    
    connection = op.get_bind()
    for req in requirements:
        # Check if exists
        exists = connection.execute(
            sa.text("SELECT 1 FROM level_roles WHERE level=:level AND role=:role"),
            {"level": req['level'], "role": req['role']}
        ).scalar()
        
        if not exists:
            op.bulk_insert(level_roles, [req])
        else:
            # Update to ensure type/count are correct
            connection.execute(
                sa.text("UPDATE level_roles SET type=:type, count_required=:count WHERE level=:level AND role=:role"),
                {"type": req['type'], "count": req['count_required'], "level": req['level'], "role": req['role']}
            )


def downgrade():
    # Revert LevelRole changes (delete them)
    op.execute("DELETE FROM level_roles WHERE role IN ('Successful Club Series', 'Better Speaker Series', 'Leadership Excellence Series')")
    
    # Revert Topicmaster spelling
    op.execute("UPDATE roles SET name = 'Topicmaster' WHERE name = 'Topicsmaster'")
    
    # Reverting whitespace trim is not really possible/desirable accurately.
