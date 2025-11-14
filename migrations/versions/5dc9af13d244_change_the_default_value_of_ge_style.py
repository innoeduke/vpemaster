"""change the default value of ge style

Revision ID: 5dc9af13d244
Revises: 
Create Date: 2025-11-14 15:16:40.930150

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5dc9af13d244'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column('Meetings', 'GE_Style',
                   server_default='One shot')

def downgrade():
    pass
