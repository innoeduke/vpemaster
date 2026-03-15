
import os
import sys
from collections import defaultdict

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Contact

def find_collisions():
    app = create_app()
    with app.app_context():
        # Get all contacts with an Avatar_URL
        contacts = Contact.query.filter(Contact.Avatar_URL.isnot(None)).all()
        
        # Group by filename
        filename_groups = defaultdict(list)
        for contact in contacts:
            filename_groups[contact.Avatar_URL].append(contact)
            
        print(f"Checking {len(filename_groups)} unique avatar filenames across {len(contacts)} contacts...")
        
        collisions_found = 0
        for filename, group in filename_groups.items():
            if len(group) > 1:
                # Check if they are actually the same person (same email or linked to same user)
                # But for now, let's just show all sharing. 
                # If they are different users/emails, it's a collision.
                
                # We'll use a simple set of user_ids to see if they are the same person
                user_ids = set()
                names = []
                for c in group:
                    names.append(f"{c.Name} (ID {c.id})")
                    for uc in c.user_club_records:
                        if uc.user_id:
                            user_ids.add(uc.user_id)
                
                # If multiple people share a file AND they don't share a user_id, it's definitely a collision.
                # Actually, even if they share a user_id, in this system they SHOULD sync.
                # But we want to KNOW who is sharing.
                
                if len(group) > 1:
                    print(f"\nFilename: {filename}")
                    print(f"  Shared by: {', '.join(names)}")
                    if len(user_ids) > 1:
                        print(f"  WARNING: Linked to DIFFERENT users: {user_ids}")
                    elif len(user_ids) == 0:
                        print(f"  WARNING: No user links found (Guests?)")
                    else:
                        print(f"  INFO: All linked to same user (ID {list(user_ids)[0]}) - This is expected sync.")
                    collisions_found += 1
        
        if collisions_found == 0:
            print("\nNo collisions found.")
        else:
            print(f"\nFound {collisions_found} filenames with potential sharing/collisions.")

if __name__ == "__main__":
    find_collisions()
