import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Role, Permission
from app.auth.permissions import Permissions

def setup_guest_role():
    app = create_app()
    with app.app_context():
        # check if Guest role exists
        guest_role = Role.query.filter_by(name='Guest').first()
        if not guest_role:
            print("Creating Guest role...")
            guest_role = Role(name='Guest', description='Unauthenticated User', level=0)
            db.session.add(guest_role)
            db.session.flush() # get ID
        else:
            print("Guest role already exists.")

        # Permissions: AGENDA_VIEW, PATHWAY_LIB_VIEW
        perms = [Permissions.AGENDA_VIEW, Permissions.PATHWAY_LIB_VIEW]
        
        for p_name in perms:
            p = Permission.query.filter_by(name=p_name).first()
            if not p:
                print(f"Adding missing permission: {p_name}")
                p = Permission(name=p_name, description=p_name)
                db.session.add(p)
            
            if p not in guest_role.permissions:
                print(f"Assigning {p_name} to Guest role.")
                guest_role.permissions.append(p)
        
        db.session.commit()
        print("Guest role setup complete.")

if __name__ == "__main__":
    setup_guest_role()
