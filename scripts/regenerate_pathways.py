
import sys
import os
import re

# Add the parent directory to the path so we can import the app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import SessionLog, Pathway

import argparse

def regenerate_pathways(apply_changes=False):
    app = create_app()
    with app.app_context():
        mode = "APPLYING CHANGES" if apply_changes else "DRY RUN"
        print(f"Starting pathway regeneration [{mode}]...")

        # 1. Build cache of all pathways (active and inactive)
        all_pathways = Pathway.query.all()
        abbr_to_name = {p.abbr: p.name for p in all_pathways if p.abbr}
        print(f"Loaded {len(abbr_to_name)} pathway abbreviations.")

        # 2. Fetch all session logs
        logs = SessionLog.query.all()
        print(f"Found {len(logs)} session logs to process.")

        updated_count = 0
        changed_preview = 0
        
        for log in logs:
            pathway_val = None

            # Priority 1: Parse current_path_level (e.g., "SR5.3")
            if log.current_path_level:
                match = re.match(r"([A-Z]+)(\d+)", log.current_path_level)
                if match:
                    abbr = match.group(1)
                    # Lookup full name
                    pathway_val = abbr_to_name.get(abbr)
            
            # Priority 2: Fallback to owner's current path
            if not pathway_val and log.owner and log.owner.Current_Path:
                pathway_val = log.owner.Current_Path

            # Check if update is needed
            if pathway_val and log.pathway != pathway_val:
                if changed_preview < 10: # Print only first 10 changes
                     print(f"Preview change Log #{log.id}: {log.pathway} -> {pathway_val}")
                
                log.pathway = pathway_val
                updated_count += 1

        print(f"Total logs with pending updates: {updated_count}")

        if apply_changes:
            try:
                db.session.commit()
                print(f"Successfully applied updates to {updated_count} logs.")
            except Exception as e:
                db.session.rollback()
                print(f"Error executing update: {e}")
        else:
            db.session.rollback() # Ensure nothing persists
            print("DRY RUN COMPLETE. No changes made.")
            print("Run with --apply to execute changes.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Regenerate pathway field in SessionLogs based on current_path_level or owner's path.")
    parser.add_argument("--apply", action="store_true", help="Apply changes to the database.")
    args = parser.parse_args()
    
    regenerate_pathways(args.apply)
