
import os
import sys
import re

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Contact

def fix_avatar_urls(apply=False):
    app = create_app()
    with app.app_context():
        # Get all contacts with an Avatar_URL
        contacts = Contact.query.filter(Contact.Avatar_URL.isnot(None)).order_by(Contact.id).all()
        
        print(f"Analyzing {len(contacts)} contacts with avatars...")
        
        avatar_dir = os.path.join(app.root_path, 'static', app.config.get('AVATAR_ROOT_DIR', 'uploads/avatars'))
        
        changes = []
        conflicts = []
        shared = {} # filename -> list of contact_ids
        
        for contact in contacts:
            filename = contact.Avatar_URL
            shared.setdefault(filename, []).append(contact.id)
            
            # Check for systematic off-by-one pattern: avatar_{id-1}.webp
            expected = f"avatar_{contact.id}.webp"
            pattern = rf"avatar_{contact.id - 1}\.webp"
            
            if re.match(pattern, filename):
                # Pattern matched! This is a corrupted record.
                changes.append({
                    'id': contact.id,
                    'name': contact.Name,
                    'old': filename,
                    'new': expected
                })
        
        print("\n--- Pattern Matches (Off-by-one) ---")
        for c in changes:
            print(f"ID {c['id']} ({c['name']}): {c['old']} -> {c['new']}")
            
        print("\n--- Shared Filenames ---")
        for filename, ids in shared.items():
            if len(ids) > 1:
                names = [Contact.query.get(cid).Name for cid in ids]
                print(f"File {filename} shared by IDs {ids} ({', '.join(names)})")
                conflicts.append({'filename': filename, 'ids': ids})

        if not apply:
            print("\nDRY RUN complete. Use --apply to fix pattern matches.")
            return

        print("\n--- Applying Fixes ---")
        fixed_count = 0
        for c in changes:
            contact = Contact.query.get(c['id'])
            # Only fix if it's NOT a shared file conflict that we haven't decided how to handle
            # Or actually, if it's shared, fixing one might help the other.
            
            # For Alice and Alvin (5 and 6), they both share avatar_5.webp.
            # Alice is 5 -> avatar_5.webp (Matches expected)
            # Alvin is 6 -> avatar_5.webp (Matches pattern avatar_{id-1})
            # So the script will propose Alvin 6: avatar_5 -> avatar_6.
            
            # Check if avatar_6 already exists and if it's used by someone else.
            # Amanda (7) has avatar_6.webp. Amanda's expected is avatar_7.webp.
            
            # It seems we should cascade the fixes?
            
        # Refined Apply Logic:
        # We'll fix ALL pattern matches. If multiple contacts end up with the same NEW filename, 
        # it's better than them having the WRONG filename.
        
        # Actually, let's just do a simple update for now.
        for c in changes:
            contact = Contact.query.get(c['id'])
            contact.Avatar_URL = c['new']
            fixed_count += 1
        
        db.session.commit()
        print(f"Fixed {fixed_count} database records.")
        print("Note: Physical file renaming is NOT handled by this script. Use manual intervention if files need moving.")

if __name__ == "__main__":
    apply = "--apply" in sys.argv
    fix_avatar_urls(apply=apply)
