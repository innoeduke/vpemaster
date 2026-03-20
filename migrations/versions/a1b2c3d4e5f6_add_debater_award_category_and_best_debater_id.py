"""add debater award category and best_debater_id

Revision ID: a1b2c3d4e5f6
Revises: 3bc5170607b7
Create Date: 2026-03-20 15:42:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '3bc5170607b7'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add 'debater' to the award_category_enum in votes table
    # For MySQL, we need to modify the ENUM column directly
    op.alter_column(
        'votes', 'award_category',
        existing_type=sa.Enum('speaker', 'evaluator', 'role-taker', 'table-topic', name='award_category_enum'),
        type_=sa.Enum('speaker', 'evaluator', 'role-taker', 'table-topic', 'debater', name='award_category_enum'),
        existing_nullable=True
    )

    # 2. Add best_debater_id column to Meetings table
    op.add_column('Meetings', sa.Column('best_debater_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_meetings_best_debater_id', 'Meetings', 'Contacts',
        ['best_debater_id'], ['id']
    )

    # 3. Update existing Debater roles in meeting_roles to have award_category='debater'
    op.execute("UPDATE meeting_roles SET award_category = 'debater' WHERE name = 'Debater' AND (award_category IS NULL OR award_category = 'none')")


def downgrade():
    # 1. Remove best_debater_id from Meetings
    op.drop_constraint('fk_meetings_best_debater_id', 'Meetings', type_='foreignkey')
    op.drop_column('Meetings', 'best_debater_id')

    # 2. Remove 'debater' from award_category_enum
    op.alter_column(
        'votes', 'award_category',
        existing_type=sa.Enum('speaker', 'evaluator', 'role-taker', 'table-topic', 'debater', name='award_category_enum'),
        type_=sa.Enum('speaker', 'evaluator', 'role-taker', 'table-topic', name='award_category_enum'),
        existing_nullable=True
    )

    # 3. Revert Debater roles back to 'none'
    op.execute("UPDATE meeting_roles SET award_category = 'none' WHERE name = 'Debater' AND award_category = 'debater'")
