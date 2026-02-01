import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import AuthRole, Permission
from app.auth.permissions import Permissions

def patch_permissions():
    app = create_app()
    with app.app_context():
        print("Patching permissions...")
        
        # 1. Create Permission if not exists
        perm_name = Permissions.RESET_PASSWORD_CLUB
        perm = Permission.query.filter_by(name=perm_name).first()
        if not perm:
            print(f"Creating permission: {perm_name}")
            perm = Permission(name=perm_name, description="Allow resetting passwords for home club members")
            db.session.add(perm)
        else:
            print(f"Permission {perm_name} already exists.")
            
        # 2. Assign to ClubAdmin
        role_name = Permissions.CLUBADMIN
        role = AuthRole.query.filter_by(name=role_name).first()
        
        if not role:
            print(f"❌ Error: Role {role_name} not found!")
            return
            
        if perm not in role.permissions:
            print(f"Assigning {perm_name} to {role_name}.")
            role.permissions.append(perm)
            db.session.commit()
            print("✅ Permission assigned successfully.")
        else:
            print(f"Permission {perm_name} already assigned to {role_name}.")

if __name__ == "__main__":
    patch_permissions()
