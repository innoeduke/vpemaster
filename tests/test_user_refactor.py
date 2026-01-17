import unittest
import sys
import os
from datetime import date

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Contact, Permission, AuthRole, UserClub, ContactClub, Club
from app.auth.permissions import Permissions
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class UserRefactorTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.client = self.app.test_client()
        self.populate_data()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def populate_data(self):
        # 1. Create Club
        self.club = Club(club_no='000000', club_name='Test Club', district='Test District')
        db.session.add(self.club)
        db.session.commit()

        # 2. Key Permissions
        perm_settings = Permission(name=Permissions.SETTINGS_VIEW_ALL, description="View Settings")
        perm_sysadmin = Permission(name=Permissions.SYSADMIN, description="Super Admin")
        db.session.add_all([perm_settings, perm_sysadmin])
        
        # 3. Roles
        self.role_admin = AuthRole(name="SysAdmin", description="Admin Role", level=10)
        self.role_user = AuthRole(name="User", description="User Role", level=1)
        db.session.add_all([self.role_admin, self.role_user])
        db.session.flush()
        
        # Assign permissions
        self.role_admin.permissions.append(perm_settings)
        self.role_admin.permissions.append(perm_sysadmin)
        
        # 4. Create Admin User
        self.admin_contact = Contact(Name="Admin User", Type="Member")
        db.session.add(self.admin_contact)
        db.session.flush()
        
        self.admin_user = User(username="admin", email="admin@test.com")
        self.admin_user.set_password("password")
        db.session.add(self.admin_user)
        db.session.flush() # Ensure ID is generated
        
        # Link Admin to Club with Role
        db.session.add(UserClub(
            user_id=self.admin_user.id, 
            club_id=self.club.id, 
            club_role_id=self.role_admin.id,
            contact_id=self.admin_contact.id
        ))
        db.session.add(ContactClub(contact_id=self.admin_contact.id, club_id=self.club.id))
        
        db.session.commit()

    def login(self):
        return self.client.post('/login', data=dict(
            username='admin@test.com',
            password='password',
            club_names=self.club.id
        ), follow_redirects=True)

    def test_create_user_via_form(self):
        """Test creating a user via the /user/form route (uses _save_user_data)."""
        self.login()
        
        # Data for new user
        new_user_data = {
            'username': 'newuser',
            'full_name': 'New User',
            'first_name': 'New',
            'last_name': 'User',
            'email': 'new@test.com',
            'phone': '1234567890',
            'status': 'active',
            'password': 'newpassword',
            'roles': [self.role_user.id] # Assign 'User' role
        }
        
        # Simulate POST (current club context needed? handled by login usually setting session)
        # We might need to ensure session['current_club_id'] is set. 
        # The login view logic usually sets it, or middleware.
        # Let's verify by manually setting cookie or trusting defaults.
        with self.client.session_transaction() as sess:
            sess['current_club_id'] = self.club.id
            
        response = self.client.post('/user/form', data=new_user_data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # Verify User Created
        user = User.query.filter_by(username='newuser').first()
        self.assertIsNotNone(user, "User should be created")
        self.assertEqual(user.email, 'new@test.com')
        self.assertEqual(user.phone, '1234567890')
        
        # Verify Contact Created and Linked
        self.assertIsNotNone(user.contact, "Contact should be linked")
        self.assertEqual(user.contact.Name, 'New User')
        self.assertEqual(user.contact.Email, 'new@test.com')
        
        # Verify Role Assigned
        user_club = UserClub.query.filter_by(user_id=user.id, club_id=self.club.id).first()
        self.assertIsNotNone(user_club, "UserClub record should exist")
        self.assertEqual(user_club.club_role_id, self.role_user.id, "User role should be assigned")

    def test_update_user_via_form(self):
        """Test updating a user via the /user/form route."""
        self.login()
        
        # Create a user to update first
        target_contact = Contact(Name="Update Target")
        db.session.add(target_contact)
        db.session.flush()
        target_user = User(username="target", email="target@test.com")
        target_user.set_password('password')
        db.session.add(target_user)
        db.session.commit()
        
        with self.client.session_transaction() as sess:
            sess['current_club_id'] = self.club.id
            
        update_data = {
            'username': 'target_updated',
            'full_name': 'Target Updated',
            'email': 'target_updated@test.com',
            'roles': [self.role_user.id]
        }
        
        response = self.client.post(f'/user/form/{target_user.id}', data=update_data, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # Verify Update
        updated_user = db.session.get(User, target_user.id)
        self.assertEqual(updated_user.username, 'target_updated')
        self.assertEqual(updated_user.email, 'target_updated@test.com')
        self.assertEqual(updated_user.contact.Name, 'Target Updated')
