"""add_amount_to_roster

Revision ID: cf09ddf03ea8
Revises: 58dd8a2c4f4c
Create Date: 2026-03-06 12:45:27.635316

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cf09ddf03ea8'
down_revision = '58dd8a2c4f4c'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add amount column
    op.add_column('roster', sa.Column('amount', sa.Float(), nullable=True))
    
    # 2. Back-fill amount from existing tickets
    op.execute("""
        UPDATE roster r 
        INNER JOIN tickets t ON r.ticket_id = t.id 
        SET r.amount = t.price
    """)


def downgrade():
    op.drop_column('roster', 'amount')
