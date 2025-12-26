import os
import re
import sys

# Standard reusable script block to handle application context
def get_app():
    # Attempt to add current directory to path if needed for local imports
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if base_dir not in sys.path:
        sys.path.append(base_dir)
        
    try:
        from app import create_app
        return create_app()
    except ImportError as e:
        print(f"Error: Could not import 'app'. Ensure this script is run from the project root or 'scripts' directory.")
        print(f"Details: {e}")
        sys.exit(1)

def clean_completed_paths(raw_value):
    if not raw_value or str(raw_value).strip().upper() == "NULL" or not str(raw_value).strip():
        return None
    
    parts = [p.strip().upper() for p in str(raw_value).split('/') if p.strip()]
    pattern = re.compile(r'^([A-Z]+)(\d+)$')
    
    valid_parts = []
    for part in parts:
        match = pattern.match(part)
        if match:
            abbr, level = match.groups()
            if level == '5':
                valid_parts.append(part)
            
    if not valid_parts:
        return None
    
    return "/".join(sorted(list(set(valid_parts))))

def clean_credentials(raw_value):
    if not raw_value or str(raw_value).strip().upper() == "NULL" or not str(raw_value).strip():
        return None
    
    val = str(raw_value).strip().upper()
    if val == "DTM":
        return "DTM"
        
    if re.match(r'^[A-Z]+\d$', val):
        return val
    
    return None

def run_cleanup(apply=False):
    app = get_app()
    with app.app_context():
        from app import db
        from app.models import Contact
        from app.achievements_utils import update_next_project
        
        contacts = Contact.query.all()
        print(f"Reviewing {len(contacts)} contacts...")
        
        changes_count = 0
        for contact in contacts:
            # Get values. Note that SQLAlchemy returns None for NULL.
            orig_paths = contact.Completed_Paths
            orig_creds = contact.credentials
            orig_next_project = contact.Next_Project
            
            new_paths = clean_completed_paths(orig_paths)
            new_creds = clean_credentials(orig_creds)
            
            # Recalculate Next_Project using the official logic
            update_next_project(contact)
            new_next_project = contact.Next_Project
            
            # Comparison: ensure we don't update if both represent "empty"
            paths_changed = new_paths != orig_paths
            creds_changed = new_creds != orig_creds
            next_project_changed = new_next_project != orig_next_project
            
            if paths_changed or creds_changed or next_project_changed:
                print(f"Contact {contact.id} ({contact.Name}):")
                if paths_changed:
                    print(f"  Paths: '{orig_paths}' -> '{new_paths}'")
                    contact.Completed_Paths = new_paths
                if creds_changed:
                    print(f"  Creds: '{orig_creds}' -> '{new_creds}'")
                    contact.credentials = new_creds
                if next_project_changed:
                    print(f"  NextProject: '{orig_next_project}' -> '{new_next_project}'")
                    # contact.Next_Project is already set by update_next_project(contact)
                
                changes_count += 1
                if apply:
                    db.session.add(contact)
        
        if apply:
            if changes_count > 0:
                db.session.commit()
                print(f"\nApplied changes to {changes_count} contacts.")
            else:
                print("\nNo changes to apply.")
        else:
            print(f"\nDRY RUN complete. {changes_count} contacts would be updated.")
            print("To apply changes, run with --apply flag.")

if __name__ == "__main__":
    apply_changes = "--apply" in sys.argv
    run_cleanup(apply=apply_changes)
