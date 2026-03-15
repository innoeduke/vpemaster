
import os
import sys
import re

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Contact

def run_recovery(apply=False):
    app = create_app()
    with app.app_context():
        avatar_dir = os.path.join(app.root_path, 'static', 'uploads', 'avatars')
        
        print("--- Step 1: Analyzing Database ---")
        contacts = Contact.query.filter(Contact.Avatar_URL.isnot(None)).all()
        db_reverts = []
        for contact in contacts:
            if contact.id == 5: continue # Skip Alice
            # If DB points to avatar_{id}.webp, it was likely changed by the broad fix
            if contact.Avatar_URL == f"avatar_{contact.id}.webp":
                db_reverts.append(contact)
        
        print(f"Found {len(db_reverts)} database records to revert.")

        print("\n--- Step 2: Analyzing Files ---")
        # Identify files on disk that match the shifted pattern
        # We need to move avatar_{n} back to avatar_{n-1}
        # ONLY for the IDs we identified in the DB
        file_actions = []
        for contact in db_reverts:
            # Current (incorrect) filename on disk should be avatar_{id}.webp
            current_file = f"avatar_{contact.id}.webp"
            target_file = f"avatar_{contact.id - 1}.webp"
            
            if os.path.exists(os.path.join(avatar_dir, current_file)):
                file_actions.append((current_file, target_file))
        
        print(f"Found {len(file_actions)} files on disk to revert.")

        if not apply:
            print("\nDRY RUN: No changes made. Use --apply to execute.")
            return

        print("\n--- Step 3: Executing Reverts ---")
        
        # 3a. Revert Files first (Shift DOWN, so sort by ID ASCENDING to avoid collision)
        file_actions.sort(key=lambda x: int(re.search(r'\d+', x[0]).group()))
        
        files_moved = 0
        for old, new in file_actions:
            old_path = os.path.join(avatar_dir, old)
            new_path = os.path.join(avatar_dir, new)
            
            # Check if target already exists (unlikely if shift was clean)
            if os.path.exists(new_path):
                print(f"WARNING: Skipping file {old} -> {new}. Target already exists.")
                continue
                
            try:
                os.rename(old_path, new_path)
                files_moved += 1
            except Exception as e:
                print(f"ERROR: Failed to move {old}: {e}")

        # 3b. Revert DB
        db_updated = 0
        for contact in db_reverts:
            contact.Avatar_URL = f"avatar_{contact.id - 1}.webp"
            db_updated += 1
        
        db.session.commit()
        
        print(f"\nRECOVERY COMPLETE:")
        print(f"- Files moved: {files_moved}")
        print(f"- DB records updated: {db_updated}")

if __name__ == "__main__":
    apply = "--apply" in sys.argv
    run_recovery(apply=apply)
