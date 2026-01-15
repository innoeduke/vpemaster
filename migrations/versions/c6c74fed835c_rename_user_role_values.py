"""rename_user_role_values

Revision ID: c6c74fed835c
Revises: fa4966cc4756
Create Date: 2026-01-15 17:13:20.086505

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c6c74fed835c'
down_revision = 'fa4966cc4756'
branch_labels = None
depends_on = None


def upgrade():
    # Rename VPE -> Operator
    op.execute("UPDATE auth_roles SET name='Operator' WHERE name='VPE'")
    # Rename Officer -> Staff
    op.execute("UPDATE auth_roles SET name='Staff' WHERE name='Officer'")
    # Rename Member -> User
    op.execute("UPDATE auth_roles SET name='User' WHERE name='Member'")


def downgrade():
    # Rename Operator -> VPE
    op.execute("UPDATE auth_roles SET name='VPE' WHERE name='Operator'")
    # Rename Staff -> Officer
    op.execute("UPDATE auth_roles SET name='Officer' WHERE name='Staff'")
    # Rename User -> Member
    op.execute("UPDATE auth_roles SET name='Member' WHERE name='User'")
