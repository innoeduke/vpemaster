import unittest
import sys
import os
from datetime import date

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Contact, Permission, AuthRole, UserClub, Club
from app.auth.permissions import Permissions
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class ProfilePermissionsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.client = self.app.test_client()
        self.setup_data()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def setup_data(self):
        # 1. Create permissions
        self.p_own = Permission(name=Permissions.PROFILE_OWN, category='profile', resource='profile')
        self.p_view = Permission(name=Permissions.PROFILE_VIEW, category='profile', resource='profile')
        self.p_edit = Permission(name=Permissions.PROFILE_EDIT, category='profile', resource='profile')
        db.session.add_all([self.p_own, self.p_view, self.p_edit])
        
        # 2. Create roles
        self.role_admin = AuthRole(name="ClubAdmin", level=4)
        self.role_staff = AuthRole(name="Staff", level=2)
        self.role_user = AuthRole(name="User", level=1)
        db.session.add_all([self.role_admin, self.role_staff, self.role_user])
        db.session.flush()
        
        # 3. Assign permissions to roles
        self.role_admin.permissions.extend([self.p_own, self.p_view, self.p_edit])
        self.role_staff.permissions.extend([self.p_own, self.p_view])
        self.role_user.permissions.extend([self.p_own])
        
        # 4. Create Club
        self.club = Club(club_no='000001', club_name='Test Club')
        db.session.add(self.club)
        db.session.flush()
        
        # 5. Create users
        self.users = {}
        role_map = {
            "ClubAdmin": self.role_admin,
            "Staff": self.role_staff,
            "User": self.role_user,
            "OtherUser": self.role_user
        }
        for role_name, role_obj in role_map.items():
            contact = Contact(Name=f"{role_name} Name", Email=f"{role_name.lower()}@test.com")
            db.session.add(contact)
            db.session.flush()
            
            user = User(username=role_name.lower(), email=contact.Email)
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            
            # Combine role level with User level (1) to ensure they have base user permissions if needed
            # though in this test we check roles specifically.
            level = role_obj.level | self.role_user.level
            db.session.add(UserClub(
                user_id=user.id,
                club_id=self.club.id,
                club_role_level=level,
                contact_id=contact.id
            ))
            self.users[role_name] = user
            
        db.session.commit()

    def login(self, username):
        return self.client.post('/login', data=dict(
            username=f"{username.lower()}@test.com",
            password="password",
            club_names=str(self.club.id)
        ), follow_redirects=True)

    def test_permission_assignment(self):
        """Test that roles have the correct permissions."""
        admin = self.users["ClubAdmin"]
        self.assertTrue(admin.has_permission(Permissions.PROFILE_OWN))
        self.assertTrue(admin.has_permission(Permissions.PROFILE_VIEW))
        self.assertTrue(admin.has_permission(Permissions.PROFILE_EDIT))
        
        self.assertTrue(self.users["Staff"].has_permission(Permissions.PROFILE_OWN))
        self.assertTrue(self.users["Staff"].has_permission(Permissions.PROFILE_VIEW))
        self.assertFalse(self.users["Staff"].has_permission(Permissions.PROFILE_EDIT))
        
        self.assertTrue(self.users["User"].has_permission(Permissions.PROFILE_OWN))
        self.assertFalse(self.users["User"].has_permission(Permissions.PROFILE_VIEW))
        self.assertFalse(self.users["User"].has_permission(Permissions.PROFILE_EDIT))

    def test_profile_access_user(self):
        """Test standard user access to profiles."""
        self.login("User")
        
        # Can view own profile
        resp = self.client.get('/profile')
        self.assertEqual(resp.status_code, 200)
        
        # Cannot view others' profiles
        other_id = self.users["OtherUser"].get_contact().id
        resp = self.client.get(f'/profile/{other_id}', follow_redirects=True)
        self.assertIn(b'Unauthorized access.', resp.data)

        # Cannot edit others' profiles
        resp = self.client.post(f'/profile/{other_id}', data={'action': 'update_profile'}, follow_redirects=True)
        self.assertIn(b'Unauthorized access.', resp.data) # Caught by GET check first if redirects

    def test_profile_access_staff(self):
        """Test staff member access to profiles."""
        self.login("Staff")
        
        # Can view own profile
        resp = self.client.get('/profile')
        self.assertEqual(resp.status_code, 200)
        
        # Can view others' profiles
        other_id = self.users["OtherUser"].get_contact().id
        resp = self.client.get(f'/profile/{other_id}')
        self.assertEqual(resp.status_code, 200)
        
        # Cannot edit others' profiles
        resp = self.client.post(f'/profile/{other_id}', data={'action': 'update_profile'}, follow_redirects=True)
        self.assertIn(b'You do not have permission to modify this profile.', resp.data)

    def test_profile_access_admin(self):
        """Test club admin access to profiles."""
        self.login("ClubAdmin")
        
        # Can view others' profiles
        other_id = self.users["OtherUser"].get_contact().id
        resp = self.client.get(f'/profile/{other_id}')
        self.assertEqual(resp.status_code, 200)
        
        # Can edit others' profiles (check for the absence of "You do not have permission")
        # Since we don't provide all form data, it might fail validation but should pass the permission check
        resp = self.client.post(f'/profile/{other_id}', data={'action': 'update_profile'}, follow_redirects=True)
        self.assertNotIn(b'You do not have permission to modify this profile.', resp.data)

if __name__ == '__main__':
    unittest.main()
