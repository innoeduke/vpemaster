import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import SessionType, MeetingRole, OwnerMeetingRoles, SessionLog
from app.constants import GLOBAL_CLUB_ID
from sqlalchemy import func

def fix_global_standards_db():
    app = create_app()
    with app.app_context():
        print(f"Fixing DB Global Standards (Target Club ID: {GLOBAL_CLUB_ID})...")
        
        # --- MEETING ROLES ---
        print("\n[Meeting Roles]")
        # 1. Identify all roles that are effectively Global (Club 1 or NULL)
        roles = MeetingRole.query.filter(
            (MeetingRole.club_id == GLOBAL_CLUB_ID) | (MeetingRole.club_id.is_(None))
        ).all()
        
        # Group by Name to find duplicates
        role_map = {} # Name -> [RoleObj]
        for r in roles:
            role_map[r.name] = role_map.get(r.name, []) + [r]
            
        for name, duplicates in role_map.items():
            if not duplicates: continue
            
            # Sort: Prefer club_id=1, then lowest ID
            duplicates.sort(key=lambda x: (0 if x.club_id == GLOBAL_CLUB_ID else 1, x.id))
            
            keep = duplicates[0]
            toss = duplicates[1:]
            
            # Ensure 'keep' has club_id=1
            if keep.club_id != GLOBAL_CLUB_ID:
                print(f" - Updating '{keep.name}' (ID {keep.id}) to Club {GLOBAL_CLUB_ID}")
                keep.club_id = GLOBAL_CLUB_ID
                
            if toss:
                print(f" - Merging {len(toss)} duplicates for '{name}' into ID {keep.id}...")
                for bad in toss:
                    print(f"   -> Removing ID {bad.id} (Club: {bad.club_id})")
                    # Remap any Foreign Keys (e.g. SessionType.role_id, OwnerMeetingRoles.role_id)
                    
                    # 1. SessionType.role_id
                    sts = SessionType.query.filter_by(role_id=bad.id).all()
                    for st in sts:
                        st.role_id = keep.id
                        
                    # 2. OwnerMeetingRoles.role_id
                    omrs = OwnerMeetingRoles.query.filter_by(role_id=bad.id).all()
                    for omr in omrs:
                        omr.role_id = keep.id
                        
                    # Delete the bad role
                    db.session.delete(bad)
        
        db.session.commit()
        print("Meeting Roles cleanup complete.")

        # --- SESSION TYPES ---
        print("\n[Session Types]")
        types = SessionType.query.filter(
            (SessionType.club_id == GLOBAL_CLUB_ID) | (SessionType.club_id.is_(None))
        ).all()
        
        type_map = {} # Title -> [SessionTypeObj]
        for t in types:
            type_map[t.Title] = type_map.get(t.Title, []) + [t]
            
        for title, duplicates in type_map.items():
            if not duplicates: continue
            
            # Sort: Prefer club_id=1, then lowest ID
            duplicates.sort(key=lambda x: (0 if x.club_id == GLOBAL_CLUB_ID else 1, x.id))
            
            keep = duplicates[0]
            toss = duplicates[1:]
            
            if keep.club_id != GLOBAL_CLUB_ID:
                print(f" - Updating '{keep.Title}' (ID {keep.id}) to Club {GLOBAL_CLUB_ID}")
                keep.club_id = GLOBAL_CLUB_ID
                
            if toss:
                print(f" - Merging {len(toss)} duplicates for '{title}' into ID {keep.id}...")
                for bad in toss:
                    print(f"   -> Removing ID {bad.id}")
                    # Remap Foreign Keys: SessionLog.Type_ID
                    logs = SessionLog.query.filter_by(Type_ID=bad.id).all()
                    for log in logs:
                        log.Type_ID = keep.id
                        
                    db.session.delete(bad)
                    
        db.session.commit()
        print("Session Types cleanup complete.")

if __name__ == "__main__":
    fix_global_standards_db()
