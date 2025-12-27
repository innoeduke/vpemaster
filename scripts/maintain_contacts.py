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

def run_cleanup(apply=False):
    app = get_app()
    with app.app_context():
        from app import db
        from app.models import Contact
        from app.achievements_utils import recalculate_contact_metadata
        
        contacts = Contact.query.all()
        print(f"Reviewing {len(contacts)} contacts...")
        
        changes_count = 0
        for contact in contacts:
            # Get values. Note that SQLAlchemy returns None for NULL.
            orig_paths = contact.Completed_Paths
            orig_creds = contact.credentials
            orig_next_project = contact.Next_Project
            orig_dtm = contact.DTM
            
            # Recalculate based on achievements (modifies contact in-place)
            # This handles DTM, Paths, Credentials, and Next_Project
            recalculate_contact_metadata(contact)
            
            new_paths = contact.Completed_Paths
            new_creds = contact.credentials
            new_next_project = contact.Next_Project
            new_dtm = contact.DTM
            
            # Sync email from linked user if contact email is blank
            orig_email = contact.Email
            new_email = orig_email
            if not orig_email or not str(orig_email).strip():
                if contact.user and contact.user.Email:
                    new_email = contact.user.Email
                    contact.Email = new_email
            
            # Comparison
            paths_changed = new_paths != orig_paths
            creds_changed = new_creds != orig_creds
            email_changed = new_email != orig_email
            next_project_changed = new_next_project != orig_next_project
            dtm_changed = new_dtm != orig_dtm
            
            if paths_changed or creds_changed or next_project_changed or email_changed or dtm_changed:
                print(f"Contact {contact.id} ({contact.Name}):")
                if paths_changed:
                    print(f"  Paths: '{orig_paths}' -> '{new_paths}'")
                if creds_changed:
                    print(f"  Creds: '{orig_creds}' -> '{new_creds}'")
                if dtm_changed:
                    print(f"  DTM: {orig_dtm} -> {new_dtm}")
                if email_changed:
                    print(f"  Email: '{orig_email}' -> '{new_email}'")
                if next_project_changed:
                    print(f"  NextProject: '{orig_next_project}' -> '{new_next_project}'")
                
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
