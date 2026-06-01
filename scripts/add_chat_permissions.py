import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import AuthRole as Role, Permission
from app.auth.permissions import Permissions

def add_chat_permissions():
    app = create_app()
    with app.app_context():
        # Create CHAT_COMMANDS
        cmd_perm = Permission.query.filter_by(name=Permissions.CHAT_COMMANDS).first()
        if not cmd_perm:
            print(f"Creating permission: {Permissions.CHAT_COMMANDS}")
            cmd_perm = Permission(
                name=Permissions.CHAT_COMMANDS, 
                description="Allow using chat terminal commands",
                category="Chat"
            )
            db.session.add(cmd_perm)
        else:
            print(f"Permission {Permissions.CHAT_COMMANDS} already exists.")
            
        # Create CHAT_AI
        ai_perm = Permission.query.filter_by(name=Permissions.CHAT_AI).first()
        if not ai_perm:
            print(f"Creating permission: {Permissions.CHAT_AI}")
            ai_perm = Permission(
                name=Permissions.CHAT_AI, 
                description="Allow talking to AI Assistant using LLM",
                category="Chat"
            )
            db.session.add(ai_perm)
        else:
            print(f"Permission {Permissions.CHAT_AI} already exists.")
            
        db.session.flush()

        # Allocate CHAT_COMMANDS and CHAT_AI to SysAdmin (and optionally ClubAdmin/Operator/Staff)
        # to ensure initial testing is possible.
        sysadmin_roles = Role.query.filter_by(name='SysAdmin').all()
        for role in sysadmin_roles:
            if cmd_perm not in role.permissions:
                print(f"Granting CHAT_COMMANDS to SysAdmin (role_id: {role.id})")
                role.permissions.append(cmd_perm)
            if ai_perm not in role.permissions:
                print(f"Granting CHAT_AI to SysAdmin (role_id: {role.id})")
                role.permissions.append(ai_perm)

        db.session.commit()
        print("Done seeding chat permissions.")

if __name__ == "__main__":
    add_chat_permissions()
