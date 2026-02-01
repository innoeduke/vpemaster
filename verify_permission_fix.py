
import sys
import os
from datetime import date
from flask import Flask

# Add local path to import app
sys.path.append(os.getcwd())

from app import create_app, db
from app.models import User, Club, UserClub, AuthRole
from app.auth.permissions import Permissions
from app.club_context import set_current_club_id

from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

def verify_permission_fix():
    app = create_app(TestConfig)
    
    with app.app_context():
        db.create_all()
        
        # 1. Setup Data
        # Club A
        club_a = Club(club_name="Club A", club_no="1111", created_at=date.today())
        db.session.add(club_a)
        
        # Club B
        club_b = Club(club_name="Club B", club_no="2222", created_at=date.today())
        db.session.add(club_b)
        
        db.session.flush()
        
        # Roles and Permissions
        # 1. Create Permission
        from app.models import Permission, RolePermission
        perm = Permission(name=Permissions.SETTINGS_VIEW_ALL, category='settings')
        db.session.add(perm)
        db.session.flush()

        club_admin_role = AuthRole.get_by_name(Permissions.CLUBADMIN)
        if not club_admin_role:
             # Create dummy if not exists (for clean test db)
             club_admin_role = AuthRole(name=Permissions.CLUBADMIN, level=100)
             db.session.add(club_admin_role)
             
        # Link Permission to Role
        if not RolePermission.query.filter_by(role_id=club_admin_role.id, permission_id=perm.id).first():
             rp = RolePermission(role_id=club_admin_role.id, permission_id=perm.id)
             db.session.add(rp)

        user_role = AuthRole.get_by_name(Permissions.USER)
        if not user_role:
             user_role = AuthRole(name=Permissions.USER, level=10)
             db.session.add(user_role)
        
        db.session.commit()

        # User: Admin in Club A, Member in Club B
        user = User(username='test_user', email='test@example.com')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        
        # Admin in A
        uc_a = UserClub(user_id=user.id, club_id=club_a.id, club_role_level=club_admin_role.level)
        db.session.add(uc_a)
        
        # Member in B
        uc_b = UserClub(user_id=user.id, club_id=club_b.id, club_role_level=user_role.level)
        db.session.add(uc_b)
        
        db.session.commit()
        
        print(f"User created with ID: {user.id}")
        print(f"Club A ID: {club_a.id} (Admin)")
        print(f"Club B ID: {club_b.id} (Member)")

        # 2. Simulate Request in Club B context
        # We need to simulate login and context
        from flask_login import login_user
        
        with app.test_request_context():
            login_user(user)
            set_current_club_id(club_b.id)
            
            from app.settings_routes import settings
            
            # The current implementation of `settings` checks `is_authorized(Permissions.SETTINGS_VIEW_ALL)`
            # `is_authorized` calls `is_club_admin(club_id)`
            # `is_club_admin` checks the specific club level.
            # HOWEVER, `is_authorized` falls back to `current_user.has_permission()`
            # And `current_user.has_permission()` checks ALL roles from ALL clubs.
            # So `is_authorized` returns True because user is Admin in Club A.
            
            print("\n--- Testing Permission for Club B (Member) ---")
            
            # Manually check what the route does
            # Route logic: 
            # if not is_authorized(Permissions.SETTINGS_VIEW_ALL): return redirect...
            
            # from app.auth.utils import is_authorized
            # has_auth = is_authorized(Permissions.SETTINGS_VIEW_ALL, club_id=club_b.id)
            
            # The route now uses is_authorized (enhanced version)
            from app.auth.utils import is_authorized
            has_auth = is_authorized(Permissions.SETTINGS_VIEW_ALL, club_id=club_b.id)
            print(f"is_authorized result: {has_auth}")
            
            if has_auth:
                print("FAIL: User IS authorized to view Club B settings (should be DENIED).")
            else:
                print("PASS: User is NOT authorized to view Club B settings.")

            # 3. Simulate Request in Club A context (Should pass)
            set_current_club_id(club_a.id)
            print("\n--- Testing Permission for Club A (Admin) ---")
            has_auth_a = is_authorized(Permissions.SETTINGS_VIEW_ALL, club_id=club_a.id)
            print(f"is_authorized result: {has_auth_a}")
            
            if has_auth_a:
                 print("PASS: User IS authorized to view Club A settings.")
            else:
                 print("FAIL: User is NOT authorized to view Club A settings (should be ALLOWED).")

if __name__ == '__main__':
    verify_permission_fix()
