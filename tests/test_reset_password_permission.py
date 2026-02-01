import sys
import os
import unittest
from datetime import date

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app import create_app, db
from app.models import User, Club, Contact, UserClub, ContactClub, AuthRole, Permission
from app.auth.permissions import Permissions
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class TestPasswordResetPermission(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Ensure SysAdmin role and permissions
        if not AuthRole.query.filter_by(name='ClubAdmin').first():
             # Basic Role Setup needed for query to work
             pass # Assuming test DB might be empty, might need minimal seeding
             
        # Seed Permissions if testing environment is empty
        perm = Permission.query.filter_by(name=Permissions.RESET_PASSWORD_CLUB).first()
        if not perm:
            perm = Permission(name=Permissions.RESET_PASSWORD_CLUB, description="Test Perm")
            db.session.add(perm)
        
        club_admin_role = AuthRole.query.filter_by(name='ClubAdmin').first()
        if not club_admin_role:
            club_admin_role = AuthRole(name='ClubAdmin', level=4)
            db.session.add(club_admin_role)
            
        if perm not in club_admin_role.permissions:
            club_admin_role.permissions.append(perm)
            
        db.session.commit()

        # Create Clubs
        self.club_a = Club(club_name="Club A", club_no="111111")
        self.club_b = Club(club_name="Club B", club_no="222222")
        db.session.add_all([self.club_a, self.club_b])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def create_user(self, username, club, role_name=None, is_home=False):
        c = Contact(Name=username, Email=f"{username}@example.com", Type='Member')
        db.session.add(c)
        db.session.flush()
        
        u = User(username=username, email=f"{username}@example.com", status='active')
        u.set_password('password')
        db.session.add(u)
        db.session.flush()
        
        role_level = 0
        if role_name:
             r = AuthRole.query.filter_by(name=role_name).first()
             if r:
                 role_level = r.level
        
        uc = UserClub(user_id=u.id, club_id=club.id, contact_id=c.id, is_home=is_home, club_role_level=role_level)
        db.session.add(uc)
        db.session.commit()
        return u

    def test_has_club_permission(self):
        # 1. Admin of Club A (Home Club)
        admin_a = self.create_user("admin_a", self.club_a, "ClubAdmin", is_home=True)
        
        # 2. Member of Club A (Home Club)
        user_a = self.create_user("user_a", self.club_a, "Member", is_home=True)
        
        # 3. Member of Club B (Home Club)
        user_b = self.create_user("user_b", self.club_b, "Member", is_home=True)
        
        # Admin A should have permission in Club A
        self.assertTrue(admin_a.has_club_permission(Permissions.RESET_PASSWORD_CLUB, self.club_a.id))
        
        # Admin A should NOT have permission in Club B
        self.assertFalse(admin_a.has_club_permission(Permissions.RESET_PASSWORD_CLUB, self.club_b.id))
        
    def test_logic_simulation(self):
        # Logic: if is_own or (home_club and has_club_permission(home_club))
        
        admin_a = self.create_user("admin_a_2", self.club_a, "ClubAdmin", is_home=True)
        user_a = self.create_user("user_a_2", self.club_a, "Member", is_home=True)
        user_b = self.create_user("user_b_2", self.club_b, "Member", is_home=True)
        
        # Case 1: Admin A resetting User A (Same Home Club) -> SHOULD ALLOW
        # user_a.home_club is Club A. Admin A has permission in Club A.
        self.assertTrue(user_a.home_club)
        self.assertTrue(admin_a.has_club_permission(Permissions.RESET_PASSWORD_CLUB, user_a.home_club.id))
        
        # Case 2: Admin A resetting User B (Different Home Club) -> SHOULD DENY
        # user_b.home_club is Club B. Admin A does NOT have permission in Club B.
        self.assertTrue(user_b.home_club)
        self.assertFalse(admin_a.has_club_permission(Permissions.RESET_PASSWORD_CLUB, user_b.home_club.id))

if __name__ == '__main__':
    unittest.main()
