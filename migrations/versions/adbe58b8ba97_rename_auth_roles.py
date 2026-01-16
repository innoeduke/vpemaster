"""rename auth roles

Revision ID: adbe58b8ba97
Revises: 74f4cf30ecc0
Create Date: 2026-01-16 11:26:59.301529

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'adbe58b8ba97'
down_revision = '74f4cf30ecc0'
branch_labels = None
depends_on = None


def upgrade():
    # Rename Admin -> SysAdmin
    op.execute("UPDATE auth_roles SET name='SysAdmin' WHERE name='Admin'")
    # Rename Operator -> ClubAdmin
    op.execute("UPDATE auth_roles SET name='ClubAdmin' WHERE name='Operator'")


def downgrade():
    # Rename SysAdmin -> Admin
    op.execute("UPDATE auth_roles SET name='Admin' WHERE name='SysAdmin'")
    # Rename ClubAdmin -> Operator
    op.execute("UPDATE auth_roles SET name='Operator' WHERE name='ClubAdmin'")
