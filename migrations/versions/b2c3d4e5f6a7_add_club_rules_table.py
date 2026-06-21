"""add club rules table

Revision ID: b2c3d4e5f6a7
Revises: 4154ec1126cf
Create Date: 2026-06-21 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = '4154ec1126cf'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'club_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('club_id', sa.Integer(), nullable=False),
        sa.Column('rule_name', sa.String(length=50), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['club_id'], ['clubs.id'], name=op.f('fk_club_rules_club_id_clubs'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_club_rules')),
        sa.UniqueConstraint('club_id', 'rule_name', name='uq_club_rule')
    )
    with op.batch_alter_table('club_rules', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_club_rules_club_id'), ['club_id'], unique=False)


def downgrade():
    with op.batch_alter_table('club_rules', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_club_rules_club_id'))

    op.drop_table('club_rules')
