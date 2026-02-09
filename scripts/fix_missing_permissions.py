import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Permission, AuthRole
from app.auth.permissions import Permissions

def fix_permissions():
    app = create_app()
    with app.app_context():
        print("Starting permission fix script...")
        
        # 1. Define missing permissions
        missing_perms = [
            {
                "name": Permissions.CONTACTS_MEMBERS_VIEW,
                "description": "View Member Contacts",
                "category": "contacts",
                "resource": "contacts",
                "action": "view_members"
            },
            {
                "name": Permissions.PROFILE_OWN,
                "description": "View and edit own profile",
                "category": "profile",
                "resource": "profile",
                "action": "view_own"
            },
             {
                "name": Permissions.PROFILE_VIEW,
                "description": "View any profile",
                "category": "profile",
                "resource": "profile",
                "action": "view"
            },
             {
                "name": Permissions.PROFILE_EDIT,
                "description": "Edit any profile",
                "category": "profile",
                "resource": "profile",
                "action": "edit"
            }
        ]
        
        for perm_data in missing_perms:
            perm = Permission.query.filter_by(name=perm_data["name"]).first()
            if not perm:
                print(f"Adding permission: {perm_data['name']}")
                perm = Permission(**perm_data)
                db.session.add(perm)
            else:
                print(f"Permission already exists: {perm_data['name']}")
        
        db.session.commit()
        
        # 2. Assign to roles
        staff_role = AuthRole.query.filter_by(name='Staff').first()
        user_role = AuthRole.query.filter_by(name='User').first()
        admin_role = AuthRole.query.filter_by(name='ClubAdmin').first()
        
        cm_view_perm = Permission.query.filter_by(name=Permissions.CONTACTS_MEMBERS_VIEW).first()
        
        if staff_role and cm_view_perm:
            if cm_view_perm not in staff_role.permissions:
                print(f"Assigning {cm_view_perm.name} to Staff role")
                staff_role.permissions.append(cm_view_perm)
        
        if user_role and cm_view_perm:
            if cm_view_perm not in user_role.permissions:
                print(f"Assigning {cm_view_perm.name} to User role")
                user_role.permissions.append(cm_view_perm)

        if admin_role and cm_view_perm:
            if cm_view_perm not in admin_role.permissions:
                print(f"Assigning {cm_view_perm.name} to ClubAdmin role")
                admin_role.permissions.append(cm_view_perm)
                
        # Also ensure profile permissions are assigned to Staff and User
        profile_perms = Permission.query.filter(Permission.name.in_([
            Permissions.PROFILE_OWN, Permissions.PROFILE_VIEW, Permissions.PROFILE_EDIT
        ])).all()
        
        for p in profile_perms:
            if admin_role and p not in admin_role.permissions:
                 admin_role.permissions.append(p)
            if staff_role and p not in staff_role.permissions:
                 staff_role.permissions.append(p)
            if user_role and p.name == Permissions.PROFILE_OWN and p not in user_role.permissions:
                 user_role.permissions.append(p)

        db.session.commit()
        print("Permission fix script completed successfully!")

if __name__ == "__main__":
    fix_permissions()
