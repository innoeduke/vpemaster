import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import AuthRole, Permission
from app.auth.permissions import Permissions

def patch_club_admin():
    app = create_app()
    with app.app_context():
        print("Patching ClubAdmin permissions...")
        
        # 1. Ensure Permission exists
        perm_name = Permissions.SETTINGS_EDIT_ALL
        p = Permission.query.filter_by(name=perm_name).first()
        if not p:
            print(f"Creating missing permission: {perm_name}")
            p = Permission(name=perm_name, description="Full access to club settings")
            db.session.add(p)
        else:
            print(f"Permission '{perm_name}' exists.")
            
        # 2. Add to ClubAdmin
        role_name = 'ClubAdmin'
        role = AuthRole.query.filter_by(name=role_name).first()
        if not role:
            print(f"❌ Role '{role_name}' NOT FOUND!")
            return

        if p not in role.permissions:
            print(f"Adding '{perm_name}' to '{role_name}' role.")
            role.permissions.append(p)
            db.session.commit()
            print("✅ Permission added.")
        else:
            print(f"ℹ️ '{role_name}' already has '{perm_name}'.")

if __name__ == "__main__":
    patch_club_admin()
