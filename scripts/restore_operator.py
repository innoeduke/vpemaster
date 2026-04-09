from app import create_app, db
from app.models import AuthRole, Permission, RolePermission
from app.auth.permissions import Permissions

def restore_operator():
    app = create_app()
    with app.app_context():
        # 1. Restore the Role
        role_name = 'Operator'
        operator = AuthRole.query.filter_by(name=role_name).first()
        if not operator:
            print(f"Restoring '{role_name}' role...")
            operator = AuthRole(name=role_name, level=3, description="Club Operator with specialized permissions")
            db.session.add(operator)
            db.session.flush() # Get ID
        else:
            print(f"'{role_name}' role already exists (ID: {operator.id}). Ensuring Level 3.")
            operator.level = 3
        
        # 2. Seed Permissions (Copy from Staff as a baseline)
        staff = AuthRole.query.filter_by(name='Staff').first()
        if staff:
            print(f"Seeding '{role_name}' permissions from 'Staff'...")
            operator_perm_ids = {p.id for p in operator.permissions}
            staff_perm_ids = {p.id for p in staff.permissions}
            
            # Additional permissions for Operator (suggested)
            # Find common permissions to add
            extra_perms = ['AGENDA_EDIT', 'SPEECH_LOGS_EDIT_ALL', 'ROSTER_EDIT', 'CONTACT_BOOK_EDIT']
            for perm_name in extra_perms:
                perm = Permission.query.filter_by(name=perm_name).first()
                if perm:
                    staff_perm_ids.add(perm.id)
            
            for pid in staff_perm_ids:
                if pid not in operator_perm_ids:
                    db.session.add(RolePermission(role_id=operator.id, permission_id=pid))
        
        db.session.commit()
        print("Restoration complete.")

if __name__ == "__main__":
    restore_operator()
