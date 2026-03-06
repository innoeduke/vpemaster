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
        # Check if ID exists before updating
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
    
    # 3. Correct Roster Assignments for Guest contacts using name/type lookups if possible
    # Check if 'type' column exists before running name/type based updates
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('tickets')]
    
    if 'type' in columns:
        # Robust subquery-based updates to find current IDs by name and type
        op.execute("""
            UPDATE roster 
            SET ticket_id = (SELECT id FROM tickets WHERE name = 'Early-bird' AND type = 'Guest' LIMIT 1)
            WHERE ticket_id = (SELECT id FROM tickets WHERE name = 'Early-bird' AND type = 'Member' LIMIT 1)
            AND contact_type = 'Guest'
        """)
        op.execute("""
            UPDATE roster 
            SET ticket_id = (SELECT id FROM tickets WHERE name = 'Walk-in' AND type = 'Guest' LIMIT 1)
            WHERE ticket_id = (SELECT id FROM tickets WHERE name = 'Walk-in' AND type = 'Member' LIMIT 1)
            AND contact_type = 'Guest'
        """)

    # Re-enable foreign key checks AT THE VERY END
    op.execute("SET FOREIGN_KEY_CHECKS = 1;")


def downgrade():
    # Disable foreign key checks
    op.execute("SET FOREIGN_KEY_CHECKS = 0;")
    
    # Check if 'type' column exists before reversing corrections
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('tickets')]

    if 'type' in columns:
        # Reverse Guest Assignment Corrections using robust lookups
        op.execute("""
            UPDATE roster 
            SET ticket_id = (SELECT id FROM tickets WHERE name = 'Early-bird' AND type = 'Member' LIMIT 1)
            WHERE ticket_id = (SELECT id FROM tickets WHERE name = 'Early-bird' AND type = 'Guest' LIMIT 1)
            AND contact_type = 'Guest'
        """)
        op.execute("""
            UPDATE roster 
            SET ticket_id = (SELECT id FROM tickets WHERE name = 'Walk-in' AND type = 'Member' LIMIT 1)
            WHERE ticket_id = (SELECT id FROM tickets WHERE name = 'Walk-in' AND type = 'Guest' LIMIT 1)
            AND contact_type = 'Guest'
        """)

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

    # Re-enable foreign key checks AT THE VERY END
    op.execute("SET FOREIGN_KEY_CHECKS = 1;")
