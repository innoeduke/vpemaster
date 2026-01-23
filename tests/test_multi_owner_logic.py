import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.session import SessionLog, SessionType
from app.models.contact import Contact
from app.services.role_service import RoleService

def test_multi_owner_save():
    app = create_app()
    with app.app_context():
        # Let's pick log 1931 as the user mentioned
        log_id = 1931
        log = db.session.get(SessionLog, log_id)
        if not log:
            print(f"Log {log_id} not found.")
            return

        print(f"Initial owners for log {log_id}: {[o.id for o in log.owners]}")
        
        # We want to add a second owner. Let's find another contact.
        # Primary owner is 78. Let's find ID 50 if exists, or just any other.
        other_contact = db.session.get(Contact, 50)
        if not other_contact:
            other_contact = Contact.query.filter(Contact.id != 78).first()
        
        if not other_contact:
            print("No other contact found to add.")
            return
            
        new_owner_ids = [78, other_contact.id]
        print(f"Attempting to set owners to: {new_owner_ids}")
        
        # Simulate RoleService call as done in agenda_routes.py
        RoleService.assign_meeting_role(log, new_owner_ids, is_admin=True)
        
        # Verify relationship before commit
        print(f"Owners in session before commit: {[o.id for o in log.owners]}")
        
        db.session.commit()
        
        # Re-fetch and verify
        db.session.expire_all()
        log = db.session.get(SessionLog, log_id)
        print(f"Final owners for log {log_id}: {[o.id for o in log.owners]}")
        
        if len(log.owners) > 1:
            print("SUCCESS: Multi-owner save verified in backend logic.")
        else:
            print("FAILURE: Multi-owner save failed in backend logic.")

if __name__ == "__main__":
    test_multi_owner_save()
