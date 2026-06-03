import unittest
import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Contact, Permission, AuthRole, ContactClub, UserClub, Club, SessionLog, SessionType, Meeting
from app.auth.permissions import Permissions
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ENGINE_OPTIONS = {}

class AddTableTopicsSpeechTestCase(unittest.TestCase):
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
        self.perm_agenda_edit = Permission(name=Permissions.MEETING_MANAGE, description="Edit Agenda", category="agenda")
        db.session.add(self.perm_agenda_edit)
        
        # 2. Create roles
        self.role_staff = AuthRole(name="Staff", level=2)
        self.role_user = AuthRole(name="User", level=1)
        db.session.add_all([self.role_staff, self.role_user])
        db.session.flush()
        
        # 3. Assign permissions
        self.role_staff.permissions.extend([self.perm_agenda_edit])
        
        # 4. Create club
        self.club = Club(club_no='000000', club_name='Test Club')
        db.session.add(self.club)
        db.session.flush()
        
        # 5. Create session type for Topics Speech
        from app.models.roster import MeetingRole
        role_topics_speaker = MeetingRole(name="Topics Speaker", type="standard", needs_approval=False, has_single_owner=True)
        db.session.add(role_topics_speaker)
        db.session.flush()

        self.st_topics_speech = SessionType(
            Title="Topics Speech",
            Duration_Min=2,
            Duration_Max=3,
            role_id=role_topics_speaker.id,
            club_id=self.club.id
        )
        db.session.add(self.st_topics_speech)
        db.session.flush()
        
        # 6. Create contacts
        self.member_contact = Contact(Name="Member User", Type="Member")
        db.session.add(self.member_contact)
        db.session.flush()
        
        db.session.add(ContactClub(contact_id=self.member_contact.id, club_id=self.club.id))
        
        # 7. Create users
        self.user_staff = User(username="staff", email="staff@test.com")
        self.user_staff.set_password("password")
        self.user_user = User(username="user", email="user@test.com")
        self.user_user.set_password("password")
        db.session.add_all([self.user_staff, self.user_user])
        db.session.flush()
        
        # Assign roles via UserClub
        db.session.add(UserClub(user_id=self.user_staff.id, club_id=self.club.id, club_role_level=self.role_staff.level, contact_id=self.member_contact.id))
        db.session.add(UserClub(user_id=self.user_user.id, club_id=self.club.id, club_role_level=self.role_user.level, contact_id=self.member_contact.id))
        
        # 8. Create a meeting
        from datetime import date
        self.meeting = Meeting(Meeting_Number=1, Meeting_Date=date.today(), club_id=self.club.id, status='not started')
        db.session.add(self.meeting)
        db.session.flush()

        # Add an initial session log
        self.session_log = SessionLog(
            meeting_id=self.meeting.id,
            Meeting_Seq=1,
            Type_ID=self.st_topics_speech.id,
            Duration_Min=2,
            Duration_Max=3,
            Session_Title="Introduction",
            Status="Booked"
        )
        db.session.add(self.session_log)
        
        db.session.commit()

    def login(self, username, password):
        return self.client.post('/login', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    def test_add_table_topics_speech_success(self):
        """Test adding table topics speech successfully with AGENDA_EDIT permission."""
        self.login("staff", "password")
        
        # Set session club_id since routes require authorized_club_required
        with self.client.session_transaction() as sess:
            sess['club_id'] = self.club.id

        response = self.client.post(f'/booking/{self.meeting.id}/add_table_topics_speech')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data['success'])

        # Verify a new session was created in db
        logs = SessionLog.query.filter_by(meeting_id=self.meeting.id).order_by(SessionLog.Meeting_Seq).all()
        self.assertEqual(len(logs), 2)
        new_log = logs[1]
        self.assertEqual(new_log.Session_Title, "Topics Speech")
        self.assertEqual(new_log.Type_ID, self.st_topics_speech.id)
        self.assertEqual(new_log.Meeting_Seq, 2)
        self.assertTrue(new_log.hidden)

    def test_add_table_topics_speech_unauthorized(self):
        """Test adding table topics speech fails for user without AGENDA_EDIT permission."""
        self.login("user", "password")
        
        # Set session club_id since routes require authorized_club_required
        with self.client.session_transaction() as sess:
            sess['club_id'] = self.club.id

        response = self.client.post(f'/booking/{self.meeting.id}/add_table_topics_speech')
        self.assertEqual(response.status_code, 403)
        data = response.get_json()
        self.assertFalse(data['success'])
        self.assertEqual(data['message'], "Unauthorized")

        # Verify NO new session was created in db
        logs = SessionLog.query.filter_by(meeting_id=self.meeting.id).all()
        self.assertEqual(len(logs), 1)
