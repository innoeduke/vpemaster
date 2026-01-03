import sys
import os
import argparse

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import SessionLog

app = create_app()

def fix_role_levels(apply=False):
    """
    Identifies SessionLog entries with missing project_code and updates them.
    This moves roles from 'Level General' to their derived levels.
    """
    with app.app_context():
        if apply:
            print("Starting Fix: Updating missing role levels (APPLY MODE)...")
        else:
            print("Starting Fix: Updating missing role levels (DRY RUN)...")
        
        # Find logs with assigned owners and missing or malformed project codes
        # We check for NULL, empty, or strings that don't look like Level codes (e.g. PI4)
        import re
        all_logs = SessionLog.query.filter(SessionLog.Owner_ID.isnot(None)).all()
        
        logs = []
        for l in all_logs:
            code = (l.project_code or "").strip()
            # If code is missing or doesn't match the pattern [A-Z]+\d+ (e.g. SR1, PI4)
            if not code or not re.match(r"^[A-Z]+\d+", code):
                logs.append(l)
        
        updated_count = 0
        skipped_count = 0
        
        for log in logs:
            old_code = log.project_code or "None"
            new_code = log.derive_project_code()
            
            if new_code:
                print(f"[{'WILL UPDATE' if not apply else 'UPDATING'}] Log #{log.id} ({log.session_type.Title if log.session_type else 'Role'}): {old_code} -> {new_code}")
                log.project_code = new_code
                updated_count += 1
            else:
                skipped_count += 1
                # print(f"[SKIPPING] Log #{log.id}: Could not derive code.")

        if updated_count > 0:
            if apply:
                db.session.commit()
                print(f"\nSuccessfully updated {updated_count} logs.")
            else:
                print(f"\nDRY RUN COMPLETE: Would have updated {updated_count} logs. Run with --apply to commit changes.")
        else:
            print("\nNo logs found that require updating.")
            
        if skipped_count > 0:
            print(f"Note: {skipped_count} logs were skipped because a level could not be derived (e.g. owner has no pathway).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix role classifications by populating missing project_codes.")
    parser.add_argument("--apply", action="store_true", help="Apply changes to the database.")
    args = parser.parse_args()
    
    fix_role_levels(apply=args.apply)
