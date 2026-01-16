import sys
import os

# Add the parent directory to sys.path to import the app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Permission, AuthRole

def init_perms():
    app = create_app()
    with app.app_context():
        print("Initializing About Club permissions...")
        
        # 1. Create permissions if they don't exist
        view_perm = Permission.query.filter_by(name='ABOUT_CLUB_VIEW').first()
        if not view_perm:
            view_perm = Permission(
                name='ABOUT_CLUB_VIEW',
                description='View club information and executive committee',
                category='club',
                resource='club',
                action='view'
            )
            db.session.add(view_perm)
            print("Created ABOUT_CLUB_VIEW permission")
            
        edit_perm = Permission.query.filter_by(name='ABOUT_CLUB_EDIT').first()
        if not edit_perm:
            edit_perm = Permission(
                name='ABOUT_CLUB_EDIT',
                description='Edit club information and executive committee',
                category='club',
                resource='club',
                action='edit'
            )
            db.session.add(edit_perm)
            print("Created ABOUT_CLUB_EDIT permission")
        
        db.session.flush() # Ensure permissions have IDs
        
        # 2. Assign ABOUT_CLUB_VIEW to all Roles
        all_roles = AuthRole.query.all()
        for role in all_roles:
            if view_perm not in role.permissions:
                role.permissions.append(view_perm)
                print(f"Assigned ABOUT_CLUB_VIEW to role: {role.name}")
        
        # 3. Assign ABOUT_CLUB_EDIT to SysAdmin and ClubAdmin
        admin_role = AuthRole.query.filter_by(name='SysAdmin').first()
        operator_role = AuthRole.query.filter_by(name='ClubAdmin').first()
        
        if admin_role and edit_perm not in admin_role.permissions:
            admin_role.permissions.append(edit_perm)
            print("Assigned ABOUT_CLUB_EDIT to SysAdmin")
            
        if operator_role and edit_perm not in operator_role.permissions:
            operator_role.permissions.append(edit_perm)
            print("Assigned ABOUT_CLUB_EDIT to ClubAdmin")
            
        db.session.commit()
        print("Done!")

if __name__ == '__main__':
    init_perms()
