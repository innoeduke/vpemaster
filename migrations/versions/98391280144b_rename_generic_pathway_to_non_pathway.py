"""rename generic pathway to non pathway

Revision ID: 98391280144b
Revises: 02cfb8111fa4
Create Date: 2026-05-18 21:07:36.108473

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '98391280144b'
down_revision = '02cfb8111fa4'
branch_labels = None
depends_on = None


def upgrade():
    # 0. Check if 'pathway' column exists in 'planner' table, add it if not
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('planner')]
    if 'pathway' not in columns:
        op.add_column('planner', sa.Column('pathway', sa.String(length=100), nullable=True))

    # 1. Update Pathways table name
    op.execute("UPDATE pathways SET name = 'Non Pathway' WHERE name = 'Generic'")
    
    # 2. Update Session_Logs pathway values
    op.execute("UPDATE Session_Logs SET pathway = 'Non Pathway' WHERE pathway = 'Generic'")
    
    # 3. Update planner pathway values
    op.execute("UPDATE planner SET pathway = 'Non Pathway' WHERE pathway = 'Generic'")
    
    # 4. Update Contacts Current_Path values
    op.execute("UPDATE Contacts SET Current_Path = 'Non Pathway' WHERE Current_Path = 'Generic'")
    
    # 5. Update achievements path_name values
    op.execute("UPDATE achievements SET path_name = 'Non Pathway' WHERE path_name = 'Generic'")


def downgrade():
    # 1. Revert Pathways table name
    op.execute("UPDATE pathways SET name = 'Generic' WHERE name = 'Non Pathway'")
    
    # 2. Revert Session_Logs pathway values
    op.execute("UPDATE Session_Logs SET pathway = 'Generic' WHERE pathway = 'Non Pathway'")
    
    # 3. Revert planner pathway values
    op.execute("UPDATE planner SET pathway = 'Generic' WHERE pathway = 'Non Pathway'")
    
    # 4. Revert Contacts Current_Path values
    op.execute("UPDATE Contacts SET Current_Path = 'Generic' WHERE Current_Path = 'Non Pathway'")
    
    # 5. Revert achievements path_name values
    op.execute("UPDATE achievements SET path_name = 'Generic' WHERE path_name = 'Non Pathway'")

    # 6. Revert adding pathway column
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('planner')]
    if 'pathway' in columns:
        op.drop_column('planner', 'pathway')
