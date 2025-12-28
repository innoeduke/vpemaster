import sys
import os
import argparse

# Add the parent directory to sys.path to allow importing from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Roster

def update_roster_contact_types(dry_run=False):
    app = create_app()
    with app.app_context():
        print("Starting Roster contact_type update...")
        
        # Fetch directly to avoid excessive queries if possible, but we need Contact and User access.
        # SQLAlchemy models allow easy traversal.
        roster_entries = Roster.query.filter(Roster.contact_id.isnot(None)).all()
        
        updated_count = 0
        skipped_count = 0
        
        for entry in roster_entries:
            if not entry.contact:
                print(f"Warning: Roster entry {entry.id} has contact_id {entry.contact_id} but no contact found.")
                continue

            # Determine contact type logic matching roster_routes.py
            contact_type = entry.contact.Type
            
            # Check if linked to a user with Officer role
            if entry.contact.user and entry.contact.user.is_officer:
                contact_type = 'Officer'
            
            current_type = entry.contact_type
            
            if current_type != contact_type:
                if dry_run:
                    print(f"[DRY RUN] Would update Entry {entry.id} (Meeting {entry.meeting_number}): {current_type} -> {contact_type}")
                else:
                    entry.contact_type = contact_type
                    updated_count += 1
            else:
                skipped_count += 1
                
        if not dry_run:
            try:
                db.session.commit()
                print(f"Successfully updated {updated_count} entries.")
            except Exception as e:
                db.session.rollback()
                print(f"Error committing changes: {e}")
        else:
            print(f"[DRY RUN] Would update {updated_count} entries.")
        
        print(f"Skipped {skipped_count} entries (already correct).")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Update contact_type in Roster table.')
    parser.add_argument('--apply', action='store_true', help='Apply changes to the database. Default is dry-run.')
    args = parser.parse_args()
    
    # Default to dry_run=True unless --apply is specified
    update_roster_contact_types(dry_run=not args.apply)
