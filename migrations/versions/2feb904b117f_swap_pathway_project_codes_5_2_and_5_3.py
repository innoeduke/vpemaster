"""swap pathway project codes 5.2 and 5.3

Revision ID: 2feb904b117f
Revises: c5304a5ed264
Create Date: 2025-11-20 17:24:24.824101

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2feb904b117f'
down_revision = 'c5304a5ed264'
branch_labels = None
depends_on = None


def upgrade():
    # Swap project codes 5.2 and 5.3 for all pathways
    connection = op.get_bind()
    
    # Define the columns to check for project codes
    code_columns = [
        'Code_DL', 'Code_EH', 'Code_MS', 
        'Code_PI', 'Code_PM', 'Code_VC', 'Code_DTM'
    ]
    
    # First, temporarily change 5.2 to a placeholder value
    for column_name in code_columns:
        connection.execute(
            sa.text(f"UPDATE Projects SET {column_name} = 'TMP2' WHERE {column_name} = '5.2'")
        )
        
    # Change 5.3 to 5.2
    for column_name in code_columns:
        connection.execute(
            sa.text(f"UPDATE Projects SET {column_name} = '5.2' WHERE {column_name} = '5.3'")
        )
        
    # Change placeholder TMP2 to 5.3
    for column_name in code_columns:
        connection.execute(
            sa.text(f"UPDATE Projects SET {column_name} = '5.3' WHERE {column_name} = 'TMP2'")
        )


def downgrade():
    # Swap project codes 5.3 and 5.2 for all pathways (reverse of upgrade)
    connection = op.get_bind()
    
    # Define the columns to check for project codes
    code_columns = [
        'Code_DL', 'Code_EH', 'Code_MS', 
        'Code_PI', 'Code_PM', 'Code_VC', 'Code_DTM'
    ]
    
    # First, temporarily change 5.2 to a placeholder value
    for column_name in code_columns:
        connection.execute(
            sa.text(f"UPDATE Projects SET {column_name} = 'TMP2' WHERE {column_name} = '5.2'")
        )
        
    # Change 5.3 to 5.2
    for column_name in code_columns:
        connection.execute(
            sa.text(f"UPDATE Projects SET {column_name} = '5.3' WHERE {column_name} = '5.3'")
        )
        
    # Change placeholder TMP2 to 5.3
    for column_name in code_columns:
        connection.execute(
            sa.text(f"UPDATE Projects SET {column_name} = '5.2' WHERE {column_name} = 'TMP2'")
        )