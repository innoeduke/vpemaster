
import os
import sys
import re

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Contact

def revert_avatar_database(apply=False):
    app = create_app()
    with app.app_context():
        # Identify contacts to revert. 
        # We only want to revert those that we "fixed" from avatar_{id-1} to avatar_{id}.
        # And we definitely want to revert Guests.
        
        contacts = Contact.query.filter(Contact.Avatar_URL.isnot(None)).all()
        
        reverts = []
        for contact in contacts:
            if contact.id == 5: continue # Alice Fan (Her new avatar is correct)
            
            # Check if it matches the pattern we set
            if contact.Avatar_URL == f"avatar_{contact.id}.webp":
                reverts.append({
                    'id': contact.id,
                    'name': contact.Name,
                    'old': contact.Avatar_URL,
                    'new': f"avatar_{contact.id - 1}.webp"
                })
        
        print(f"Proposed database reverts for {len(reverts)} contacts...")
        for r in reverts:
            print(f"ID {r['id']} ({r['name']}): {r['old']} -> {r['new']}")
            
        if not apply:
            print("\nDry run. Use --apply to execute.")
            return
            
        count = 0
        for r in reverts:
            contact = Contact.query.get(r['id'])
            contact.Avatar_URL = r['new']
            count += 1
            
        db.session.commit()
        print(f"Reverted {count} database records.")

if __name__ == "__main__":
    apply = "--apply" in sys.argv
    revert_avatar_database(apply=apply)
