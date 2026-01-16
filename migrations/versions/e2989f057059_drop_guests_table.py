"""drop guests table

Revision ID: e2989f057059
Revises: 87b7a610c0d4
Create Date: 2026-01-17 02:44:09.954264

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'e2989f057059'
down_revision = '87b7a610c0d4'
branch_labels = None
depends_on = None


def upgrade():
    # Drop guests table
    op.drop_table('guests')


def downgrade():
    op.create_table('guests',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('club_id', sa.Integer(), autoincrement=False, nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('phone', sa.String(length=50), nullable=True),
    sa.Column('email', sa.String(length=120), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('type', sa.String(length=50), nullable=True),
    sa.Column('created_date', sa.DateTime(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['club_id'], ['clubs.id']),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('guests', schema=None) as batch_op:
        batch_op.create_index('ix_guests_club_id', ['club_id'], unique=False)
