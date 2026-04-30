"""add is_officer to contact_clubs

Revision ID: b5d8fb847901
Revises: a5c9ea967902
Create Date: 2026-04-30 08:25:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b5d8fb847901'
down_revision = 'a5c9ea967902'
branch_labels = None
depends_on = None


def upgrade():
    # Add the column with a server_default so existing rows get '0' (False)
    op.add_column('contact_clubs', sa.Column('is_officer', sa.Boolean(), nullable=False, server_default=sa.text('0')))


def downgrade():
    op.drop_column('contact_clubs', 'is_officer')
