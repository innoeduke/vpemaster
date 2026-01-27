import csv
import io
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.roster import MeetingRole
from app.models.session import SessionType
from app.constants import GLOBAL_CLUB_ID

def populate_global_data():
    app = create_app()
    with app.app_context():
        print(f"Populating Global Data into Club {GLOBAL_CLUB_ID}...")
        
        # --- Step 1: Migrate existing NULL records (Legacy Globals) to Club 1 ---
        # We prioritize these to preserve IDs and relationships (SessionTypes, Logs, etc.)
        
        print("Migrating existing NULL club_id MeetingRoles to Club 1...")
        null_roles = MeetingRole.query.filter_by(club_id=None).all()
        for r in null_roles:
            # Check for conflict with existing Club 1 role
            conflict = MeetingRole.query.filter_by(name=r.name, club_id=GLOBAL_CLUB_ID).first()
            if conflict:
                print(f"Conflict: Role '{r.name}' exists in Club 1 (ID: {conflict.id}) and Global NULL (ID: {r.id}).")
                # Heuristic: The NULL role is likely the legacy one with usage history. 
                # The Club 1 role might be newly created or less used.
                # To preserve history, we should keep the NULL role (and move it to 1).
                # We delete the 'conflict' role to make space.
                # WARNING: This assumes the Club 1 role is disposable (e.g. created by failed previous run).
                print(f"Deleting conflicting Club 1 role ID {conflict.id} to preserve legacy.")
                db.session.delete(conflict)
                db.session.flush() # Ensure delete happens before update
                
            print(f"Migrating Role '{r.name}' (ID: {r.id}) to Club 1")
            r.club_id = GLOBAL_CLUB_ID
            
        print("Migrating existing NULL club_id SessionTypes to Club 1...")
        null_types = SessionType.query.filter_by(club_id=None).all()
        for st in null_types:
            conflict = SessionType.query.filter_by(Title=st.Title, club_id=GLOBAL_CLUB_ID).first()
            if conflict:
                print(f"Conflict: SessionType '{st.Title}' exists in Club 1 (ID: {conflict.id}) and Global NULL (ID: {st.id}).")
                print(f"Deleting conflicting Club 1 session type ID {conflict.id} to preserve legacy.")
                db.session.delete(conflict)
                db.session.flush()
                
            print(f"Migrating SessionType '{st.Title}' (ID: {st.id}) to Club 1")
            st.club_id = GLOBAL_CLUB_ID
            
        db.session.commit()
        
        # --- Step 2: Backfill from CSV (Only missing items) ---
        
        # Roles
        roles_path = os.path.join(app.root_path, 'meeting_roles.csv')
        if os.path.exists(roles_path):
            print(f"Checking for missing roles from {roles_path}")
            with open(roles_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    name = row.get('name')
                    if not name: continue
                    
                    # Check if exists in Global Club (now Club 1)
                    exists = MeetingRole.query.filter_by(name=name, club_id=GLOBAL_CLUB_ID).first()
                    if not exists:
                        print(f"Adding Missing Global Role: {name}")
                        new_role = MeetingRole(
                            name=name,
                            icon=row.get('icon'),
                            type=row.get('type'),
                            award_category=row.get('award_category'),
                            needs_approval=row.get('needs_approval', '0').strip() == '1',
                            has_single_owner=row.get('has_single_owner', '0').strip() == '1',
                            is_member_only=row.get('is_member_only', '0').strip() == '1',
                            club_id=GLOBAL_CLUB_ID
                        )
                        db.session.add(new_role)
        
        # Session Types is tricky due to role_id mapping. 
        # We skip auto-populating Types for now to avoid creating bad links, 
        # relying on the expectation that standard types were already in DB as NULLs.
        # If needed, we can implement smart lookup by role name.
        
        db.session.commit()
        print("Global Data Population Completed.")

if __name__ == "__main__":
    populate_global_data()
