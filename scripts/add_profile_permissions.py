import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import AuthRole as Role, Permission
from app.auth.permissions import Permissions

def add_profile_permissions():
    app = create_app()
    with app.app_context():
        # 1. Define Permissions
        profile_perms = [
            {
                'name': Permissions.PROFILE_OWN,
                'description': "allow to view and edit one's own profile, including reset one's own password",
                'category': 'profile',
                'resource': 'profile'
            },
            {
                'name': Permissions.PROFILE_VIEW,
                'description': "allow to view all users' profiles",
                'category': 'profile',
                'resource': 'profile'
            },
            {
                'name': Permissions.PROFILE_EDIT,
                'description': "allow to edit all users' profiles",
                'category': 'profile',
                'resource': 'profile'
            }
        ]

        # 2. Create Permissions in DB
        permission_objs = {}
        for perm_data in profile_perms:
            perm = Permission.query.filter_by(name=perm_data['name']).first()
            if not perm:
                print(f"Creating permission: {perm_data['name']}")
                perm = Permission(
                    name=perm_data['name'],
                    description=perm_data['description'],
                    category=perm_data['category'],
                    resource=perm_data['resource']
                )
                db.session.add(perm)
                db.session.flush()
            else:
                print(f"Permission {perm_data['name']} already exists. Updating details.")
                perm.description = perm_data['description']
                perm.category = perm_data['category']
                perm.resource = perm_data['resource']
            permission_objs[perm_data['name']] = perm

        # 3. Assign to Roles
        # PROFILE_OWN -> User (level 1+)
        # PROFILE_VIEW -> Staff (level 2+)
        # PROFILE_EDIT -> ClubAdmin (level 4+)
        
        roles_config = [
            (Permissions.PROFILE_OWN, 1),
            (Permissions.PROFILE_VIEW, 2),
            (Permissions.PROFILE_EDIT, 4)
        ]

        for perm_name, min_level in roles_config:
            perm_obj = permission_objs[perm_name]
            roles = Role.query.filter(Role.level >= min_level).all()
            for role in roles:
                if perm_obj not in role.permissions:
                    print(f"Granting {perm_name} to {role.name}")
                    role.permissions.append(perm_obj)
                else:
                    print(f"{role.name} already has {perm_name}")

        db.session.commit()
        print("Profile permissions setup complete.")

if __name__ == "__main__":
    add_profile_permissions()
