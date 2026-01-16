"""merge multiple heads

Revision ID: c149e90eeb0e
Revises: adbe58b8ba97, e020518bf358
Create Date: 2026-01-16 15:24:17.363001

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c149e90eeb0e'
down_revision = ('adbe58b8ba97', 'e020518bf358')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
