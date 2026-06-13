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
        self.perm_roster_view = Permission(name=Permissions.ROSTER_VIEW, description="View Roster", category="roster")
        self.perm_members_self = Permission(name=Permissions.MEMBERS_SELF, description="Own Bookings & Profile", category="members")
        self.perm_sl_manage = Permission(name=Permissions.SPEECH_LOGS_MANAGE, description="Manage Speech Logs", category="speech_logs")
        db.session.add_all([self.perm_roster_view, self.perm_members_self, self.perm_sl_manage])
        
        # 2. Create roles
        self.role_staff = AuthRole(name="Staff", level=2)
        self.role_user = AuthRole(name="Member", level=1)
        db.session.add_all([self.role_staff, self.role_user])
        db.session.flush()
        
        # 3. Assign permissions
        self.role_staff.permissions.extend([self.perm_roster_view, self.perm_members_self, self.perm_sl_manage])
        self.role_user.permissions.extend([self.perm_roster_view, self.perm_members_self])
        
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
        
        # 7. Create LevelRole entries to allow roadmap rendering
        from app.models.project import LevelRole
        lr1 = LevelRole(level=1, role="Prepared Speech", type="speech", count_required=3, band=0)
        lr2 = LevelRole(level=1, role="Timer", type="role", count_required=1, band=1)
        db.session.add_all([lr1, lr2])
        
        db.session.commit()

    def login(self, username, password):
        return self.client.post('/login', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    def test_user_without_roster_view_cannot_see_contacts(self):
        """Test that a user without ROSTER_VIEW permission cannot see contacts."""
        self.role_user.permissions.remove(self.perm_roster_view)
        db.session.commit()
        
        self.login("user", "password")
        # Contact list is now fetched via API
        response = self.client.get('/api/contacts/all')
        self.assertEqual(response.status_code, 403)

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
        self.assertNotIn('id="add-plan-btn"', html)
        self.assertNotIn("New Item", html)

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

    def test_user_sees_new_item_on_own_profile(self):
        """Test that a user can see the '+New Item' button on their own profile."""
        self.login("user", "password")
        with self.client.session_transaction() as sess:
            sess['club_id'] = self.club.id
        
        response = self.client.get(f'/speech_logs?speaker_id={self.member_contact.id}')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Member User", html)
        self.assertIn('id="add-plan-btn"', html)
        self.assertIn("New Item", html)

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

    def test_kpi_member_count_alignment(self):
        """Test that the Total Members KPI count on the contacts page matches the members page count."""
        # Grant MEMBERS_MANAGE to the staff role so they can access the members page
        perm_members_manage = Permission(name=Permissions.MEMBERS_MANAGE, description="Manage Members", category="members")
        db.session.add(perm_members_manage)
        self.role_staff.permissions.append(perm_members_manage)
        
        # Add a Member contact without a User account
        extra_contact = Contact(Name="Extra Member No User", Type="Member")
        db.session.add(extra_contact)
        db.session.flush()
        db.session.add(ContactClub(contact_id=extra_contact.id, club_id=self.club.id))
        db.session.commit()

        # Login as staff (who can view both settings/members and contacts)
        self.login("staff", "password")

        # Set session current club context
        with self.client.session_transaction() as sess:
            sess['current_club_id'] = self.club.id

        # 1. Fetch contacts page, check Total Members KPI value using regex
        response = self.client.get('/contacts')
        self.assertEqual(response.status_code, 200)
        html_contacts = response.get_data(as_text=True)
        
        import re
        contacts_member_stat = re.search(r'style="color:\s*#28a745"[^>]*>\s*(\d+)\s*</div>', html_contacts)
        self.assertIsNotNone(contacts_member_stat)
        # We expect 2 active users, not 3 member contacts
        self.assertEqual(contacts_member_stat.group(1), "2")

        # 2. Fetch members page, check Total Members KPI value
        response = self.client.get('/users')
        self.assertEqual(response.status_code, 200)
        html_users = response.get_data(as_text=True)
        
        users_member_stat = re.search(r'style="color:\s*#28a745"[^>]*>\s*(\d+)\s*</div>', html_users)
        self.assertIsNotNone(users_member_stat)
        self.assertEqual(users_member_stat.group(1), "2")

if __name__ == '__main__':
    unittest.main()
