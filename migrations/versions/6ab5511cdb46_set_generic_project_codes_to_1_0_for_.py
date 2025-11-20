"""set generic project codes to 1.0 for project id 60

Revision ID: 6ab5511cdb46
Revises: 2feb904b117f
Create Date: 2025-11-20 17:32:21.317652

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6ab5511cdb46'
down_revision = '2feb904b117f'
branch_labels = None
depends_on = None


def upgrade():
    # Set all Code_?? columns to "1.0" for the generic project with ID = 60
    connection = op.get_bind()
    
    # Define the columns to update
    code_columns = [
        'Code_DL', 'Code_EH', 'Code_MS', 
        'Code_PI', 'Code_PM', 'Code_VC'
    ]
    
    # Update each column for project ID 60
    for column_name in code_columns:
        connection.execute(
            sa.text(f"UPDATE Projects SET {column_name} = '1.0' WHERE ID = 60")
        )


def downgrade():
    # In downgrade, we can't restore the previous values since we don't know what they were
    # So we'll set them back to NULL (which is what they likely were before)
    connection = op.get_bind()
    
    # Define the columns to update
    code_columns = [
        'Code_DL', 'Code_EH', 'Code_MS', 
        'Code_PI', 'Code_PM', 'Code_VC'
    ]
    
    # Set each column back to NULL for project ID 60
    for column_name in code_columns:
        connection.execute(
            sa.text(f"UPDATE Projects SET {column_name} = NULL WHERE ID = 60")
        )