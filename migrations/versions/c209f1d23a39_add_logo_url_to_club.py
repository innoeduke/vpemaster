"""add logo_url to club

Revision ID: c209f1d23a39
Revises: ba394717d770
Create Date: 2026-01-24 15:44:27.101019

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c209f1d23a39'
down_revision = 'ba394717d770'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('clubs')]

    if 'logo_url' not in columns:
        with op.batch_alter_table('clubs', schema=None) as batch_op:
            batch_op.add_column(sa.Column('logo_url', sa.String(length=255), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('clubs')]
    
    if 'logo_url' in columns:
        with op.batch_alter_table('clubs', schema=None) as batch_op:
            batch_op.drop_column('logo_url')
