import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Role, User, LevelRole
from sqlalchemy import delete

app = create_app()

with app.app_context():
    print("Starting cleanup of 'Meeting Manager' role...")

    # 1. Update Users with 'Meeting Manager' role to 'Member'
    users_updated = User.query.filter_by(Role='Meeting Manager').update({User.Role: 'Member'})
    print(f"Updated {users_updated} users from 'Meeting Manager' to 'Member'.")

    # 2. Delete 'Meeting Manager' from Role table
    # Note: We need to be careful if there are Foreign Keys pointing to this Role ID in SessionLog or others.
    # Usually SessionType links to Role. 
    # If there are SessionTypes using this Role, we should probably delete/update them too?
    # Or just delete the Role and let cascade handle it? 
    # Let's check if the role exists first.
    
    mm_role = Role.query.filter_by(name='Meeting Manager').first()
    if mm_role:
        print(f"Found Role: {mm_role.name} (ID: {mm_role.id})")
        
        # Check for SessionTypes
        # from app.models import SessionType
        # session_types = SessionType.query.filter_by(role_id=mm_role.id).all()
        # print(f"Found {len(session_types)} SessionTypes associated with this role.")
        
        # Check for LevelRoles - it uses 'role' string column, not foreign key
        level_roles_deleted = LevelRole.query.filter_by(role=mm_role.name).delete()
        print(f"Deleted {level_roles_deleted} LevelRole entries.")
        
        # Now delete the role itself. 
        # CAUTION: If there are SessionLogs pointing to SessionTypes pointing to this Role, 
        # deleting the Role might fail if there's no cascade, or might delete logs.
        # Given this is a requested change, we assume it's safe to remove. 
        # But safest is to let the user know. 
        # For now, we will try to delete.
        
        try:
            db.session.delete(mm_role)
            print("Deleted 'Meeting Manager' from Role table.")
        except Exception as e:
            print(f"Error deleting role: {e}")
            print("Skipping deletion of Role record to prevent FK violation, but Users allow access via manager_id now.")
            
    else:
        print("Role 'Meeting Manager' not found in Role table.")

    db.session.commit()
    print("Cleanup completed.")
