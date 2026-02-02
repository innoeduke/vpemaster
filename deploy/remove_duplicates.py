
import sys
import os
import argparse
from collections import defaultdict

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.session import SessionLog

def remove_duplicates(execute=False):
    app = create_app()
    with app.app_context():
        print(f"--- Duplicate Log Removal (Execute: {execute}) ---")
        
        # Fetch all logs
        logs = SessionLog.query.order_by(SessionLog.Meeting_Number, SessionLog.Meeting_Seq).all()
        
        # Group by unique characteristics
        # Key: (Meeting_Number, Meeting_Seq, Title, Type_ID, Start_Time, Owners)
        # Including Owners ensures we don't merge distinct Topics Speeches (different people).
        # Including Meeting_Seq ensures we don't merge sequentially distinct items.
        grouped = defaultdict(list)
        
        for log in logs:
            # Normalize Start_Time string representation
            start_str = str(log.Start_Time) if log.Start_Time else "None"
            
            # Create a frozen set or tuple of owner IDs for the key
            owner_ids = tuple(sorted([o.id for o in log.owners]))
            
            key = (log.Meeting_Number, log.Meeting_Seq, log.Session_Title, log.Type_ID, start_str, owner_ids)
            grouped[key].append(log)
            
        duplicates_found = 0
        deleted_count = 0
        
        for key, group in grouped.items():
            if len(group) > 1:
                duplicates_found += 1
                
                # Sort group: 
                # Primary sort: Has owners? (True first)
                # Secondary sort: ID (Lower first - keeping original)
                # Note: valid owners check might trigger DB query
                
                def sort_key(l):
                    has_owner = 1 if l.owners else 0
                    return (-has_owner, l.id)
                
                group.sort(key=sort_key)
                
                winner = group[0]
                losers = group[1:]
                
                print(f"Duplicate Found: Meeting {key[0]} - '{key[1]}' ({len(group)} copies)")
                print(f"  Keep: ID {winner.id} (Owners: {len(winner.owners)})")
                
                for loser in losers:
                    print(f"  Delete: ID {loser.id} (Owners: {len(loser.owners)})")
                    if execute:
                        # Clean up associations? 
                        # OwnerMeetingRoles should cascade logic or be checked.
                        # If OwnerMeetingRoles points to this log, it should be deleted or moved?
                        # If duplicate has NO owners, it has no OwnerMeetingRoles.
                        # If checks above prioritize logs WITH owners, we are effectively deleting empty ones.
                        # If both have owners, we might lose data if we just delete. 
                        # But sort prioritizes keeping one with owners.
                        # If multiple have owners, manual check needed? 
                        # Assuming perfect duplicates (including owners) or empty duplicates.
                        
                        db.session.delete(loser)
                        deleted_count += 1
        
        if duplicates_found == 0:
            print("No duplicates found.")
        else:
            print(f"Found {duplicates_found} sets of duplicates.")
            if execute:
                db.session.commit()
                print(f"Deleted {deleted_count} duplicate logs.")
            else:
                print(f"Dry run. Would delete {len(logs) - len(grouped) + (duplicates_found - len(grouped) if False else 0)} ???")
                # Calc is strictly: sum(len(g)-1 for g in grouped if len(g)>1)
                to_delete = sum(len(g)-1 for g in grouped.values() if len(g)>1)
                print(f"Dry run. Would delete {to_delete} logs.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true', help='Execute deletions')
    args = parser.parse_args()
    
    remove_duplicates(execute=args.execute)
