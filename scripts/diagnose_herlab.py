import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Club, User, UserClub, AuthRole, Permission
from app.auth.permissions import Permissions

def diagnose_herlab():
    app = create_app()
    with app.app_context():
        print("Diagnosing Herlab Club Admin Issue...")
        
        # 1. content: Check ClubAdmin Role Permissions
        role_name = 'ClubAdmin'
        role = AuthRole.query.filter_by(name=role_name).first()
        if not role:
            print(f"❌ Role '{role_name}' NOT FOUND.")
            return

        print(f"Role '{role_name}' permissions:")
        has_settings_edit = False
        for p in role.permissions:
            print(f"  - {p.name}")
            if p.name == Permissions.SETTINGS_EDIT_ALL:
                has_settings_edit = True
        
        if has_settings_edit:
            print(f"✅ Role '{role_name}' HAS '{Permissions.SETTINGS_EDIT_ALL}'.")
        else:
            print(f"❌ Role '{role_name}' MISSING '{Permissions.SETTINGS_EDIT_ALL}'.")

        # 2. Check Herlab Club
        club = Club.query.filter(Club.club_name.ilike('%Herlab%')).first()
        if not club:
            print("❌ Club 'Herlab' NOT FOUND.")
            return
            
        print(f"Club found: {club.club_name} (ID: {club.id})")
        
        # 3. Check Members and Roles
        user_clubs = UserClub.query.filter_by(club_id=club.id).all()
        print(f"Found {len(user_clubs)} memberships.")
        
        found_admin = False
        for uc in user_clubs:
            user = User.query.get(uc.user_id)
            print(f"  - User: {user.username} (ID: {user.id})")
            print(f"    - Role Level: {uc.club_role_level}")
            
            # Check what roles this level corresponds to
            roles = []
            # This logic mimics User.get_user_club(club_id).roles BUT manually here
            # We need to fetch all roles and check bitmask
            all_roles = AuthRole.query.all()
            for r in all_roles:
                if (uc.club_role_level & r.level) == r.level:
                    roles.append(r.name)
            
            print(f"    - Roles: {', '.join(roles)}")
            
            if 'ClubAdmin' in roles:
                found_admin = True
                
        if found_admin:
            print("✅ Found at least one ClubAdmin in Herlab.")
        else:
            print("❌ NO ClubAdmin found in Herlab.")

if __name__ == "__main__":
    diagnose_herlab()
