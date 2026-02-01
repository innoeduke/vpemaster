import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import MeetingRole, SessionType, OwnerMeetingRoles
from app.models.roster import RosterRole
from app.constants import GLOBAL_CLUB_ID

def clean_redundant_roles():
    app = create_app()
    with app.app_context():
        print("Starting cleanup of redundant local standard roles...")
        
        # 1. Get Global Roles for mapping
        global_roles = MeetingRole.query.filter_by(club_id=GLOBAL_CLUB_ID).all()
        global_map = {r.name: r for r in global_roles}
        
        # 2. Find local 'standard' roles
        local_standards = MeetingRole.query.filter(
            MeetingRole.type == 'standard',
            MeetingRole.club_id != GLOBAL_CLUB_ID,
            MeetingRole.club_id.isnot(None)
        ).all()
        
        print(f"Found {len(local_standards)} redundant roles to process.")
        
        for bad in local_standards:
            if bad.name not in global_map:
                print(f" - Skipping '{bad.name}' (ID {bad.id}, Club {bad.club_id}): No Global match found.")
                continue
            
            good = global_map[bad.name]
            print(f" - Merging '{bad.name}' (ID {bad.id}, Club {bad.club_id}) -> Global (ID {good.id})")
            
            # Remap SessionType
            sts = SessionType.query.filter_by(role_id=bad.id).all()
            for st in sts:
                st.role_id = good.id
                
            # Remap OwnerMeetingRoles
            omrs = OwnerMeetingRoles.query.filter_by(role_id=bad.id).all()
            for omr in omrs:
                omr.role_id = good.id
                
            # Remap RosterRole
            rrs = RosterRole.query.filter_by(role_id=bad.id).all()
            for rr in rrs:
                rr.role_id = good.id
                
            # Delete redundant role
            db.session.delete(bad)
            
        db.session.commit()
        print("Cleanup complete.")

if __name__ == "__main__":
    clean_redundant_roles()
