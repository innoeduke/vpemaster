import sys
import os
import shutil

# Ensure the root project directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.contact import Contact
from app.models.user import User

def move_physical_files(app):
    static_dir = os.path.join(app.root_path, 'static')
    dest_dir = os.path.join(static_dir, 'avatars')
    
    src_dirs = [
        os.path.join(static_dir, 'uploads', 'avatars'),
        os.path.join(static_dir, 'upload', 'avatars')
    ]
    
    found_src = None
    for src in src_dirs:
        if os.path.exists(src) and os.path.isdir(src):
            found_src = src
            break
            
    if not found_src:
        print("⚠️ No source avatars folder found to move. Checked:")
        for src in src_dirs:
            print(f"  - {src}")
        # Ensure destination directory is still created
        os.makedirs(dest_dir, exist_ok=True)
        print(f"Created/verified destination directory: {dest_dir}")
        return
        
    print(f"📂 Found source avatars folder: {found_src}")
    os.makedirs(dest_dir, exist_ok=True)
    
    files_moved = 0
    for item in os.listdir(found_src):
        if item.startswith('.'):  # Skip hidden files like .DS_Store
            continue
        s_path = os.path.join(found_src, item)
        d_path = os.path.join(dest_dir, item)
        
        if os.path.isdir(s_path):
            print(f"Skipping subdirectory: {item}")
            continue
            
        try:
            if os.path.exists(d_path):
                print(f"Replacing existing file in destination: {item}")
                os.remove(d_path)
            shutil.move(s_path, d_path)
            files_moved += 1
        except Exception as e:
            print(f"Error moving file {item}: {e}")
            
    print(f"✅ Successfully moved {files_moved} files to {dest_dir}")
    
    # Try to clean up and remove old source directory if it's empty
    try:
        # Remove leftover hidden files
        for item in os.listdir(found_src):
            os.remove(os.path.join(found_src, item))
        os.rmdir(found_src)
        print(f"🗑️ Removed old source directory: {found_src}")
    except Exception as e:
        print(f"Could not remove old source directory {found_src}: {e}")


def update_database_records():
    print("🗄️ Querying database to update avatar URLs...")
    
    # Update Contacts table
    contacts = Contact.query.filter(Contact.Avatar_URL.isnot(None)).all()
    contacts_updated = 0
    for contact in contacts:
        old_url = contact.Avatar_URL
        new_url = old_url
        
        # Replace variations of uploads/avatars/ or upload/avatars/
        if 'uploads/avatars/' in old_url:
            new_url = old_url.replace('uploads/avatars/', 'avatars/')
        elif 'upload/avatars/' in old_url:
            new_url = old_url.replace('upload/avatars/', 'avatars/')
            
        if new_url != old_url:
            contact.Avatar_URL = new_url
            contacts_updated += 1
            print(f"  Contact ID {contact.id}: {old_url} ➡️ {new_url}")
            
    # Update users table
    users = User.query.filter(User.avatar_url.isnot(None)).all()
    users_updated = 0
    for user in users:
        old_url = user.avatar_url
        new_url = old_url
        
        if 'uploads/avatars/' in old_url:
            new_url = old_url.replace('uploads/avatars/', 'avatars/')
        elif 'upload/avatars/' in old_url:
            new_url = old_url.replace('upload/avatars/', 'avatars/')
            
        if new_url != old_url:
            user.avatar_url = new_url
            users_updated += 1
            print(f"  User ID {user.id}: {old_url} ➡️ {new_url}")
            
    if contacts_updated > 0 or users_updated > 0:
        db.session.commit()
        print(f"✅ Committed updates: {contacts_updated} Contacts, {users_updated} users updated.")
    else:
        print("ℹ️ No database records needed updating (all records are already correct or are stored as plain filenames).")


def main():
    app = create_app()
    with app.app_context():
        print("Starting avatars migration...")
        move_physical_files(app)
        update_database_records()
        print("Migration complete!")

if __name__ == '__main__':
    main()
