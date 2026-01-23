import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Permission
from app.auth.permissions import Permissions

def fix_media_permission():
    app = create_app()
    with app.app_context():
        perm_name = Permissions.MEDIA_ACCESS
        perm = Permission.query.filter_by(name=perm_name).first()
        
        if perm:
            print(f"Updating permission: {perm_name}")
            print(f"Old category: {perm.category}")
            # print(f"Old resource: {perm.resource}")
            
            # Use lowercase to match existing convention
            perm.category = "agenda" 
            perm.resource = "agenda"
            
            db.session.commit()
            print(f"New category: {perm.category}")
            print(f"New resource: {perm.resource}")
            print("Successfully updated.")
        else:
            print(f"Permission {perm_name} not found.")

if __name__ == "__main__":
    fix_media_permission()
