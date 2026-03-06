"""add_club_id_to_tickets

Revision ID: b76d8ef01dd1
Revises: cf09ddf03ea8
Create Date: 2026-03-06 12:52:02.390197

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b76d8ef01dd1'
down_revision = 'cf09ddf03ea8'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add club_id column
    op.add_column('tickets', sa.Column('club_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_tickets_club_id'), 'tickets', ['club_id'], unique=False)
    op.create_foreign_key(op.f('fk_tickets_club_id_clubs'), 'tickets', 'clubs', ['club_id'], ['id'])

    # 2. Set existing tickets to correct club_id (2)
    # Using raw SQL to avoid dependency on global constant in migration if possible.
    op.execute("UPDATE tickets SET club_id = 2")

    # 3. Final sync of roster amounts from ticket prices
    # Note: This will sync based on current ticket prices in the database.
    op.execute("""
        UPDATE roster r 
        INNER JOIN tickets t ON r.ticket_id = t.id 
        SET r.amount = t.price
    """)


def downgrade():
    op.drop_constraint(op.f('fk_tickets_club_id_clubs'), 'tickets', type_='foreignkey')
    op.drop_index(op.f('ix_tickets_club_id'), table_name='tickets')
    op.drop_column('tickets', 'club_id')
