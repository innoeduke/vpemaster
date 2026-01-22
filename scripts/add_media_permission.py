import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import AuthRole as Role, Permission
from app.auth.permissions import Permissions

def add_media_permission():
    app = create_app()
    with app.app_context():
        # 1. Create Permission
        perm_name = Permissions.MEDIA_ACCESS
        perm = Permission.query.filter_by(name=perm_name).first()
        if not perm:
            print(f"Creating permission: {perm_name}")
            perm = Permission(name=perm_name, description="Access to external media URLs")
            db.session.add(perm)
            db.session.flush()
        else:
            print(f"Permission {perm_name} already exists.")
            
        # 2. Assign to all authenticated roles (Level >= 1)
        # Assuming Guest is 0. User=1, Staff=2, ClubAdmin=4, SysAdmin=8
        roles = Role.query.filter(Role.level >= 1).all()
        
        count = 0
        for role in roles:
            if perm not in role.permissions:
                print(f"Granting {perm_name} to {role.name}")
                role.permissions.append(perm)
                count += 1
            else:
                print(f"{role.name} already has {perm_name}")
                
        db.session.commit()
        print(f"Done. Granted to {count} roles.")

if __name__ == "__main__":
    add_media_permission()
