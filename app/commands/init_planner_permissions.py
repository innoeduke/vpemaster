import click
from flask.cli import with_appcontext
from app import db
from app.models import Permission, AuthRole, RolePermission
from app.auth.permissions import Permissions

@click.command('init-planner-permissions')
@with_appcontext
def init_planner_permissions():
    """Initialize planner permissions and assign to roles."""
    print("Initializing planner permissions...")
    
    # 1. Create Permissions
    planner_view = Permission.query.filter_by(name=Permissions.PLANNER_VIEW).first()
    if not planner_view:
        planner_view = Permission(
            name=Permissions.PLANNER_VIEW,
            description='Allow viewing own planner entries',
            category='planner',
            resource='planner',
            action='view'
        )
        db.session.add(planner_view)
        print(f"Created permission: {Permissions.PLANNER_VIEW}")
    
    planner_edit = Permission.query.filter_by(name=Permissions.PLANNER_EDIT).first()
    if not planner_edit:
        planner_edit = Permission(
            name=Permissions.PLANNER_EDIT,
            description='Allow creating/editing own planner entries',
            category='planner',
            resource='planner',
            action='edit'
        )
        db.session.add(planner_edit)
        print(f"Created permission: {Permissions.PLANNER_EDIT}")
    
    db.session.flush() # Get IDs
    
    # 2. Assign to Roles
    # Roles that should have planner access: User, Staff, ClubAdmin, SysAdmin
    role_names = [Permissions.USER, Permissions.STAFF, Permissions.CLUBADMIN, Permissions.SYSADMIN]
    
    for role_name in role_names:
        role = AuthRole.query.filter_by(name=role_name).first()
        if role:
            # Assign PLANNER_VIEW
            if not any(p.name == Permissions.PLANNER_VIEW for p in role.permissions):
                role.permissions.append(planner_view)
                print(f"Assigned {Permissions.PLANNER_VIEW} to {role_name}")
            
            # Assign PLANNER_EDIT
            if not any(p.name == Permissions.PLANNER_EDIT for p in role.permissions):
                role.permissions.append(planner_edit)
                print(f"Assigned {Permissions.PLANNER_EDIT} to {role_name}")
        else:
            print(f"Warning: Role {role_name} not found")
            
    db.session.commit()
    print("Permissions initialization complete.")

if __name__ == '__main__':
    init_planner_permissions()
