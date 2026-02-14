import unittest
import sys
import os
from datetime import date

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Contact, Permission, AuthRole, ContactClub, UserClub, Club
from app.auth.permissions import Permissions
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class ContactsPermissionTestCase(unittest.TestCase):
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
        db.engine.dispose()
        self.app_context.pop()

    def setup_data(self):
        # 1. Create permissions
        self.perm_cb_view = Permission(name=Permissions.CONTACT_BOOK_VIEW, description="View All Contacts", category="contacts")
        self.perm_cm_view = Permission(name=Permissions.CONTACTS_MEMBERS_VIEW, description="View Member Contacts", category="contacts")
        db.session.add_all([self.perm_cb_view, self.perm_cm_view])
        
        # 2. Create roles
        self.role_staff = AuthRole(name="Staff", level=2)
        self.role_user = AuthRole(name="User", level=1)
        db.session.add_all([self.role_staff, self.role_user])
        db.session.flush()
        
        # 3. Assign permissions
        self.role_staff.permissions.append(self.perm_cb_view)
        self.role_staff.permissions.append(self.perm_cm_view)
        self.role_user.permissions.append(self.perm_cm_view)
        
        # 4. Create club
        self.club = Club(club_no='000000', club_name='Test Club')
        db.session.add(self.club)
        db.session.flush()
        
        # 5. Create contacts
        self.member_contact = Contact(Name="Member User", Type="Member")
        self.guest_contact = Contact(Name="Guest User", Type="Guest")
        db.session.add_all([self.member_contact, self.guest_contact])
        db.session.flush()
        
        db.session.add(ContactClub(contact_id=self.member_contact.id, club_id=self.club.id))
        db.session.add(ContactClub(contact_id=self.guest_contact.id, club_id=self.club.id))
        
        # 6. Create users
        self.user_staff = User(username="staff", email="staff@test.com")
        self.user_staff.set_password("password")
        self.user_user = User(username="user", email="user@test.com")
        self.user_user.set_password("password")
        db.session.add_all([self.user_staff, self.user_user])
        db.session.flush()
        
        # Assign roles via UserClub
        db.session.add(UserClub(user_id=self.user_staff.id, club_id=self.club.id, club_role_level=self.role_staff.level, contact_id=self.member_contact.id))
        db.session.add(UserClub(user_id=self.user_user.id, club_id=self.club.id, club_role_level=self.role_user.level, contact_id=self.member_contact.id))
        
        db.session.commit()

    def login(self, username, password):
        return self.client.post('/login', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    def test_user_sees_only_members(self):
        """Test that a regular user only sees Member type contacts."""
        self.login("user", "password")
        # Contact list is now fetched via API
        response = self.client.get('/api/contacts/all')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        names = [c['Name'] for c in data]
        self.assertIn("Member User", names)
        self.assertNotIn("Guest User", names)

    def test_staff_sees_all_contacts(self):
        """Test that staff sees all contacts."""
        self.login("staff", "password")
        # Contact list is now fetched via API
        response = self.client.get('/api/contacts/all')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        names = [c['Name'] for c in data]
        self.assertIn("Member User", names)
        self.assertIn("Guest User", names)

if __name__ == '__main__':
    unittest.main()
