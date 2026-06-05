import unittest
import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Contact, Permission, AuthRole, ContactClub, UserClub, Club, SessionLog, SessionType, Meeting
from app.auth.permissions import Permissions
from app.agenda_routes import recalculate_section_ids
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ENGINE_OPTIONS = {}

class TestSectionGrouping(unittest.TestCase):
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
        # Create permissions and roles
        self.perm_agenda_edit = Permission(name=Permissions.MEETING_MANAGE, description="Edit Agenda", category="agenda")
        db.session.add(self.perm_agenda_edit)
        
        self.role_staff = AuthRole(name="Staff", level=2)
        db.session.add(self.role_staff)
        db.session.flush()
        
        self.role_staff.permissions.extend([self.perm_agenda_edit])
        
        self.club = Club(club_no='000000', club_name='Test Club')
        db.session.add(self.club)
        db.session.flush()
        
        # Create session types
        self.st_section = SessionType(Title="Section Header", Is_Section=True, club_id=self.club.id)
        self.st_regular = SessionType(Title="Regular Session", Is_Section=False, club_id=self.club.id)
        db.session.add_all([self.st_section, self.st_regular])
        db.session.flush()

        self.member_contact = Contact(Name="Member User", Type="Member")
        db.session.add(self.member_contact)
        db.session.flush()
        db.session.add(ContactClub(contact_id=self.member_contact.id, club_id=self.club.id))

        self.user_staff = User(username="staff", email="staff@test.com")
        self.user_staff.set_password("password")
        db.session.add(self.user_staff)
        db.session.flush()
        
        db.session.add(UserClub(user_id=self.user_staff.id, club_id=self.club.id, club_role_level=self.role_staff.level, contact_id=self.member_contact.id))
        
        from datetime import date
        self.meeting = Meeting(Meeting_Number=1, Meeting_Date=date.today(), club_id=self.club.id, status='not started')
        db.session.add(self.meeting)
        db.session.commit()

    def login(self, username, password):
        return self.client.post('/login', data=dict(
            username=username,
            password=password
        ), follow_redirects=True)

    def test_recalculate_section_ids(self):
        """Test that recalculate_section_ids properly groups logs by sections."""
        # Create logs in sequence:
        # 1: Section 1
        # 2: Regular 1 (under Section 1)
        # 3: Regular 2 (under Section 1)
        # 4: Section 2
        # 5: Regular 3 (under Section 2)
        log1 = SessionLog(meeting_id=self.meeting.id, Meeting_Seq=1, Type_ID=self.st_section.id, Session_Title="Sec 1")
        log2 = SessionLog(meeting_id=self.meeting.id, Meeting_Seq=2, Type_ID=self.st_regular.id, Session_Title="Reg 1")
        log3 = SessionLog(meeting_id=self.meeting.id, Meeting_Seq=3, Type_ID=self.st_regular.id, Session_Title="Reg 2")
        log4 = SessionLog(meeting_id=self.meeting.id, Meeting_Seq=4, Type_ID=self.st_section.id, Session_Title="Sec 2")
        log5 = SessionLog(meeting_id=self.meeting.id, Meeting_Seq=5, Type_ID=self.st_regular.id, Session_Title="Reg 3")
        
        db.session.add_all([log1, log2, log3, log4, log5])
        db.session.flush()

        recalculate_section_ids(self.meeting)
        db.session.commit()

        # Check section IDs
        self.assertEqual(log1.section_id, log1.id)
        self.assertEqual(log2.section_id, log1.id)
        self.assertEqual(log3.section_id, log1.id)
        self.assertEqual(log4.section_id, log4.id)
        self.assertEqual(log5.section_id, log4.id)

    def test_recalculate_section_ids_with_reorder(self):
        """Test section_id recalculation when logs are re-ordered/updated."""
        log1 = SessionLog(meeting_id=self.meeting.id, Meeting_Seq=1, Type_ID=self.st_section.id, Session_Title="Sec 1")
        log2 = SessionLog(meeting_id=self.meeting.id, Meeting_Seq=2, Type_ID=self.st_regular.id, Session_Title="Reg 1")
        log3 = SessionLog(meeting_id=self.meeting.id, Meeting_Seq=3, Type_ID=self.st_section.id, Session_Title="Sec 2")
        
        db.session.add_all([log1, log2, log3])
        db.session.flush()

        recalculate_section_ids(self.meeting)
        self.assertEqual(log2.section_id, log1.id)
        self.assertEqual(log3.section_id, log3.id)

        # Swap sequences: log3 is now Seq 2, log2 is Seq 3
        log3.Meeting_Seq = 2
        log2.Meeting_Seq = 3
        db.session.flush()

        recalculate_section_ids(self.meeting)
        # Now log2 is after log3 (Sec 2), so its section_id should be log3.id
        self.assertEqual(log2.section_id, log3.id)
        self.assertEqual(log3.section_id, log3.id)
        self.assertEqual(log1.section_id, log1.id)

    def test_recalculate_section_ids_with_deletion(self):
        """Test section_id recalculation when a section is deleted."""
        log1 = SessionLog(meeting_id=self.meeting.id, Meeting_Seq=1, Type_ID=self.st_section.id, Session_Title="Sec 1")
        log2 = SessionLog(meeting_id=self.meeting.id, Meeting_Seq=2, Type_ID=self.st_regular.id, Session_Title="Reg 1")
        log3 = SessionLog(meeting_id=self.meeting.id, Meeting_Seq=3, Type_ID=self.st_section.id, Session_Title="Sec 2")
        log4 = SessionLog(meeting_id=self.meeting.id, Meeting_Seq=4, Type_ID=self.st_regular.id, Session_Title="Reg 2")
        
        db.session.add_all([log1, log2, log3, log4])
        db.session.flush()

        recalculate_section_ids(self.meeting)
        self.assertEqual(log2.section_id, log1.id)
        self.assertEqual(log4.section_id, log3.id)

        # Delete Sec 2
        db.session.delete(log3)
        db.session.flush()

        # Recalculate
        recalculate_section_ids(self.meeting)
        # Now Reg 2 (log4) should fall back to Section 1 (log1)
        self.assertEqual(log4.section_id, log1.id)
