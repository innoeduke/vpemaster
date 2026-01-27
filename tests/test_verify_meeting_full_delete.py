
import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Meeting, Roster, RosterRole, Contact
from app.models.roster import MeetingRole
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:' # Use in-memory DB or configured test DB
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = True

class TestMeetingDeletion(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Create Club (required for Meeting)
        from app.models import Club
        self.club = Club(
            club_no='000000',
            club_name='Test Club',
            district='Test District'
        )
        db.session.add(self.club)
        db.session.commit()
        
        # Setup Data
        self.meeting_num = 8888
        self.meeting = Meeting(Meeting_Number=self.meeting_num, status='finished', club_id=self.club.id)
        db.session.add(self.meeting)
        
        # Seed Guest Role and Permission for authorized_club_required
        from app.models import Permission, AuthRole as Role
        from app.auth.permissions import Permissions
        
        perm = Permission(name=Permissions.ABOUT_CLUB_VIEW, description="View Club")
        perm_agenda = Permission(name=Permissions.AGENDA_VIEW, description="View Agenda")
        role = Role(name='Guest', description='Guest')
        role.permissions.append(perm)
        role.permissions.append(perm_agenda)
        db.session.add_all([perm, perm_agenda, role])
        db.session.commit()
        
        self.contact = Contact(Name="Delete Test User")
        db.session.add(self.contact)
        
        self.role = MeetingRole(name="Delete Test Role", type="generic", needs_approval=False, has_single_owner=False)
        db.session.add(self.role)
        db.session.commit()
        
        # Create Roster Entry
        self.roster = Roster(meeting_number=self.meeting_num, contact_id=self.contact.id, order_number=1)
        db.session.add(self.roster)
        db.session.commit()
        
        # Link Role to Roster (creates RosterRole)
        self.roster.roles.append(self.role)
        db.session.commit()
        
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_full_deletion(self):
        """Test that deleting a meeting removes Roster and RosterRole entries"""
        # Verify existence
        self.assertIsNotNone(Meeting.query.filter_by(Meeting_Number=self.meeting_num).first())
        self.assertIsNotNone(Roster.query.filter_by(meeting_number=self.meeting_num).first())
        # Join lookup
        roster_role_exists = db.session.query(RosterRole).filter_by(roster_id=self.roster.id).first()
        self.assertIsNotNone(roster_role_exists)
        
        # Capture ID before deletion
        roster_id = self.roster.id
        
        # Set session context for authorized_club_required
        with self.client.session_transaction() as sess:
            sess['current_club_id'] = self.club.id
            
        # Perform Deletion via Route
        response = self.client.post(f'/agenda/status/{self.meeting_num}')
        self.assertEqual(response.status_code, 200, f"Response: {response.json}")
        self.assertTrue(response.json.get('deleted'), "Should return deleted=True")
        
        # Verify Deletion
        self.assertIsNone(Meeting.query.filter_by(Meeting_Number=self.meeting_num).first())
        self.assertIsNone(Roster.query.filter_by(meeting_number=self.meeting_num).first())
        
        # Verify RosterRole is gone
        roster_role_remaining = db.session.query(RosterRole).filter_by(roster_id=roster_id).first()
        self.assertIsNone(roster_role_remaining)

if __name__ == '__main__':
    unittest.main()
