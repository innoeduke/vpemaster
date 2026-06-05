from app import create_app, db
from sqlalchemy import text

def sync_roles():
    app = create_app()
    with app.app_context():
        # 1. Map Levels to IDs
        # Based on my previous lookup:
        # ID: 1, Name: SysAdmin, Level: 8
        # ID: 2, Name: ClubAdmin, Level: 4
        # ID: 6, Name: Operator, Level: 3 (Custom/Legacy mapping)
        # ID: 3, Name: Staff, Level: 2
        # ID: 4, Name: Member, Level: 1
        # ID: 5, Name: Guest, Level: 0
        
        # We'll use a hierarchy search for bitmasks
        role_map = [
            (8, 1), # SysAdmin
            (4, 2), # ClubAdmin
            (3, 6), # Operator
            (2, 3), # Staff
            (1, 4), # Member
        ]
        
        print("Fetching users with missing auth_role_id...")
        rows = db.session.execute(text("SELECT id, club_role_level, auth_role_id FROM user_clubs")).fetchall()
        
        update_count = 0
        for row_id, level, current_role_id in rows:
            if current_role_id is not None:
                continue
            
            target_role_id = None
            if level == 0:
                target_role_id = 5 # Guest
            else:
                # Find the highest level bitmask that matches
                # For bitmasks, we check (level & bit) == bit
                # Special case for Level 3 (Operator) if it was stored as 3
                if level == 3:
                    target_role_id = 6
                else:
                    for bit, rid in role_map:
                        if (level & bit) == bit:
                            target_role_id = rid
                            break
            
            if target_role_id:
                db.session.execute(
                    text("UPDATE user_clubs SET auth_role_id = :rid WHERE id = :ucid"),
                    {'rid': target_role_id, 'ucid': row_id}
                )
                update_count += 1
        
        db.session.commit()
        print(f"Synced {update_count} users to new auth_role_id system.")

if __name__ == "__main__":
    sync_roles()
