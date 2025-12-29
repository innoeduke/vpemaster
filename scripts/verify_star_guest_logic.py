import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Contact, SessionLog, SessionType, Role, Meeting
from sqlalchemy import func

def verify_star_logic():
    app = create_app()
    with app.app_context():
        # 1. Fetch counts using the new logic
        distinct_roles = db.session.query(
            SessionLog.Owner_ID, SessionLog.Meeting_Number, SessionType.role_id, Role.name
        ).select_from(SessionLog).join(SessionType).join(Role).filter(
            SessionLog.Owner_ID.isnot(None),
            SessionType.role_id.isnot(None),
            Role.type.in_(['standard', 'club-specific'])
        ).distinct().all()

        contact_tt_count = {}
        contact_other_role_count = {}

        for owner_id, _, _, role_name in distinct_roles:
            r_name = role_name.strip() if role_name else ""
            if r_name == "Topics Speaker":
                contact_tt_count[owner_id] = contact_tt_count.get(owner_id, 0) + 1
            else:
                contact_other_role_count[owner_id] = contact_other_role_count.get(owner_id, 0) + 1

        # Awards
        best_tt_map = {}
        best_tt_counts = db.session.query(
            Meeting.best_table_topic_id, func.count(Meeting.id)
        ).filter(Meeting.best_table_topic_id.isnot(None)).group_by(Meeting.best_table_topic_id).all()
        
        for c_id, count in best_tt_counts:
            best_tt_map[c_id] = count

        # Check a few contacts
        contacts = Contact.query.all()
        qualified_guests = []
        for c in contacts:
            tt = contact_tt_count.get(c.id, 0)
            best_tt = best_tt_map.get(c.id, 0)
            other_roles = contact_other_role_count.get(c.id, 0)
            
            # Replicating the logic from check_membership_qualification
            is_qualified = (tt >= 4 and best_tt >= 1 and other_roles >= 2)
            
            if is_qualified:
                qualified_guests.append(f"{c.Name} (ID: {c.id}) [TT: {tt}, BestTT: {best_tt}, Other: {other_roles}]")
                
        print(f"Found {len(qualified_guests)} Qualified Guests:")
        for s in qualified_guests:
            print(f" - {s}")

if __name__ == "__main__":
    verify_star_logic()
