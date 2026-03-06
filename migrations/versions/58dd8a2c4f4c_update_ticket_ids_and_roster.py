"""update_ticket_ids_and_roster

Revision ID: 58dd8a2c4f4c
Revises: 367907ecdf72
Create Date: 2026-03-06 12:00:33.563590

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '58dd8a2c4f4c'
down_revision = '367907ecdf72'
branch_labels = None
depends_on = None


def upgrade():
    # Disable foreign key checks to allow ID updates
    op.execute("SET FOREIGN_KEY_CHECKS = 0;")
    
    # 1. Park IDs as negative values to avoid collisions
    # IDs involved: 2, 5, 9, 4, 10
    ids = [2, 5, 9, 4, 10]
    for id_val in ids:
        op.execute(f"UPDATE tickets SET id = -{id_val} WHERE id = {id_val}")
        op.execute(f"UPDATE roster SET ticket_id = -{id_val} WHERE ticket_id = {id_val}")
    
    # 2. Apply requested mapping:
    # -2 -> 5 (Role-taker)
    # -5 -> 9 (Voucher)
    # -9 -> 2 (Early-bird Guest)
    # -4 -> 10 (Officer)
    # -10 -> 4 (Walk-in Guest)
    mapping = {
        -2: 5,
        -5: 9,
        -9: 2,
        -4: 10,
        -10: 4
    }
    
    for old, new in mapping.items():
        op.execute(f"UPDATE tickets SET id = {new} WHERE id = {old}")
        op.execute(f"UPDATE roster SET ticket_id = {new} WHERE ticket_id = {old}")
    
    # Re-enable foreign key checks
    op.execute("SET FOREIGN_KEY_CHECKS = 1;")

    # 3. Correct Roster Assignments for Guest contacts
    # - ticket_id 1 (Early-bird Member) -> 2 (Early-bird Guest)
    # - ticket_id 3 (Walk-in Member) -> 4 (Walk-in Guest)
    op.execute("UPDATE roster SET ticket_id = 2 WHERE ticket_id = 1 AND contact_type = 'Guest'")
    op.execute("UPDATE roster SET ticket_id = 4 WHERE ticket_id = 3 AND contact_type = 'Guest'")


def downgrade():
    # Reverse Guest Assignment Corrections first (best effort)
    # Move them back to Member IDs if they are Guests
    op.execute("UPDATE roster SET ticket_id = 1 WHERE ticket_id = 2 AND contact_type = 'Guest'")
    op.execute("UPDATE roster SET ticket_id = 3 WHERE ticket_id = 4 AND contact_type = 'Guest'")

    # Disable foreign key checks
    op.execute("SET FOREIGN_KEY_CHECKS = 0;")
    
    # Reverse mapping for downgrade:
    # 5 -> 2
    # 9 -> 5
    # 2 -> 9
    # 10 -> 4
    # 4 -> 10
    
    # 1. Park IDs as negative values
    final_ids = [5, 9, 2, 10, 4]
    for id_val in final_ids:
        op.execute(f"UPDATE tickets SET id = -{id_val} WHERE id = {id_val}")
        op.execute(f"UPDATE roster SET ticket_id = -{id_val} WHERE ticket_id = {id_val}")
        
    # 2. Revert to original IDs:
    # -5 -> 2
    # -9 -> 5
    # -2 -> 9
    # -10 -> 4
    # -4 -> 10
    reverse_mapping = {
        -5: 2,
        -9: 5,
        -2: 9,
        -10: 4,
        -4: 10
    }
    
    for old, new in reverse_mapping.items():
        op.execute(f"UPDATE tickets SET id = {new} WHERE id = {old}")
        op.execute(f"UPDATE roster SET ticket_id = {new} WHERE ticket_id = {old}")

    # Re-enable foreign key checks
    op.execute("SET FOREIGN_KEY_CHECKS = 1;")
