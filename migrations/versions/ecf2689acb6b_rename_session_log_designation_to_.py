"""rename_session_log_designation_to_credentials

Revision ID: ecf2689acb6b
Revises: d033e89c2364
Create Date: 2025-11-26 09:57:50.864455

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'ecf2689acb6b'
down_revision = 'd033e89c2364'
branch_labels = None
depends_on = None


def upgrade():
    # Rename Designation to credentials
    op.alter_column('Session_Logs', 'Designation', new_column_name='credentials',
                    existing_type=mysql.VARCHAR(255), nullable=True, existing_server_default=None)


def downgrade():
    # Rename credentials to Designation
    op.alter_column('Session_Logs', 'credentials', new_column_name='Designation',
                    existing_type=mysql.VARCHAR(255), nullable=True, existing_server_default=None)