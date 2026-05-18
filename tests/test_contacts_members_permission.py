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
    SQLALCHEMY_ENGINE_OPTIONS = {}

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
        self.perm_sl_view_own = Permission(name=Permissions.SPEECH_LOGS_VIEW_OWN, description="View Own Speech Logs", category="speech_logs")
        self.perm_sl_edit_all = Permission(name=Permissions.SPEECH_LOGS_EDIT_ALL, description="Edit All Speech Logs", category="speech_logs")
        db.session.add_all([self.perm_cb_view, self.perm_cm_view, self.perm_sl_view_own, self.perm_sl_edit_all])
        
        # 2. Create roles
        self.role_staff = AuthRole(name="Staff", level=2)
        self.role_user = AuthRole(name="User", level=1)
        db.session.add_all([self.role_staff, self.role_user])
        db.session.flush()
        
        # 3. Assign permissions
        self.role_staff.permissions.extend([self.perm_cb_view, self.perm_cm_view, self.perm_sl_view_own, self.perm_sl_edit_all])
        self.role_user.permissions.extend([self.perm_cm_view, self.perm_sl_view_own])
        
        # 4. Create club
        self.club = Club(club_no='000000', club_name='Test Club')
        db.session.add(self.club)
        db.session.flush()
        
        # 5. Create contacts
        self.member_contact = Contact(Name="Member User", Type="Member")
        self.guest_contact = Contact(Name="Guest User", Type="Guest")
        self.other_member_contact = Contact(Name="Other Member User", Type="Member")
        db.session.add_all([self.member_contact, self.guest_contact, self.other_member_contact])
        db.session.flush()
        
        db.session.add(ContactClub(contact_id=self.member_contact.id, club_id=self.club.id))
        db.session.add(ContactClub(contact_id=self.guest_contact.id, club_id=self.club.id))
        db.session.add(ContactClub(contact_id=self.other_member_contact.id, club_id=self.club.id))
        
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

    def test_user_can_view_other_member_speech_logs(self):
        """Test that a regular user with CONTACTS_MEMBERS_VIEW can view other members' speech logs."""
        self.login("user", "password")
        # We need to simulate being in the club's context
        with self.client.session_transaction() as sess:
            sess['club_id'] = self.club.id
        
        response = self.client.get(f'/speech_logs?speaker_id={self.other_member_contact.id}')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Other Member User", html)

    def test_user_cannot_view_guest_speech_logs(self):
        """Test that a regular user cannot view guest speech logs, falling back to their own logs."""
        self.login("user", "password")
        # We need to simulate being in the club's context
        with self.client.session_transaction() as sess:
            sess['club_id'] = self.club.id
            
        response = self.client.get(f'/speech_logs?speaker_id={self.guest_contact.id}')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        # Should fall back to their own logs (Member User) and NOT show Guest User logs
        self.assertIn("Member User", html)
        self.assertNotIn("Guest User", html)

    def test_complete_speech_log_success(self):
        """Test that completing a speech log succeeds and returns the progress HTML without KeyError."""
        from app.models.meeting import Meeting
        from app.models.session import SessionLog, SessionType
        from app.models.roster import MeetingRole

        self.login("staff", "password")

        # 1. Create meeting, role, session type, and session log
        meeting = Meeting(club_id=self.club.id, Meeting_Number=969, status='finished', Meeting_Date=date(2026, 4, 15))
        db.session.add(meeting)
        db.session.flush()

        role = MeetingRole(name="Prepared Speaker", type="standard", needs_approval=False, has_single_owner=True)
        db.session.add(role)
        db.session.flush()

        st = SessionType(Title="Prepared Speech", role_id=role.id, club_id=self.club.id)
        db.session.add(st)
        db.session.flush()

        log = SessionLog(meeting_id=meeting.id, Type_ID=st.id, Status="booked")
        db.session.add(log)
        db.session.flush()

        # Add an owner record
        from app.models.session import OwnerMeetingRoles
        omr = OwnerMeetingRoles(meeting_id=meeting.id, role_id=role.id, contact_id=self.member_contact.id, session_log_id=log.id)
        db.session.add(omr)
        db.session.commit()

        # We need to simulate being in the club's context
        with self.client.session_transaction() as sess:
            sess['club_id'] = self.club.id

        # 2. Call complete speech log endpoint
        response = self.client.post(f'/speech_log/complete/{log.id}')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])

if __name__ == '__main__':
    unittest.main()
