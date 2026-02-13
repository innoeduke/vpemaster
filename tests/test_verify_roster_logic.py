
import unittest
import sys
import os

# Add project root to path ensuring 'app' can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Roster, Contact
from app.models.roster import MeetingRole
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = True

class TestVerifyRosterLogic(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Setup Data
        self.meeting_num = 9999
        
        self.officer_contact = Contact(Name="Test Officer", Type="Officer")
        self.member_contact = Contact(Name="Test Member", Type="Member")
        self.guest_contact = Contact(Name="Test Guest", Type="Guest")
        
        self.role = MeetingRole(name="Test Role", type="functionary", needs_approval=False, has_single_owner=False)
        
        db.session.add_all([self.officer_contact, self.member_contact, self.guest_contact, self.role])
        
        # Seed Tickets
        from app.models import Ticket, Meeting
        tickets = [
            Ticket(name="Officer", price=0),
            Ticket(name="Early-bird (Member)", price=0),
            Ticket(name="Role-taker", price=0),
            Ticket(name="Guest", price=0)
        ]
        db.session.add_all(tickets)
        
        from datetime import date
        self.meeting = Meeting(Meeting_Number=self.meeting_num, Meeting_Date=date(2025, 1, 1), club_id=1)
        db.session.add(self.meeting)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def test_roster_sync_logic(self):
        """Verify roster synchronization logic for different contact types"""
        
        # 1. Officer Assignment
        Roster.sync_role_assignment(self.meeting.id, self.officer_contact.id, self.role, 'assign')
        db.session.commit()
        
        officer_entry = Roster.query.filter_by(meeting_id=self.meeting.id, contact_id=self.officer_contact.id).first()
        self.assertGreaterEqual(officer_entry.order_number, 1000)
        self.assertEqual(officer_entry.ticket.name, "Officer")

        # 2. Member Assignment
        Roster.sync_role_assignment(self.meeting.id, self.member_contact.id, self.role, 'assign')
        db.session.commit()
        
        member_entry = Roster.query.filter_by(meeting_id=self.meeting.id, contact_id=self.member_contact.id).first()
        self.assertIsNone(member_entry.order_number)
        self.assertEqual(member_entry.ticket.name, "Early-bird (Member)")

        # 3. Guest Assignment
        Roster.sync_role_assignment(self.meeting.id, self.guest_contact.id, self.role, 'assign')
        db.session.commit()
        
        guest_entry = Roster.query.filter_by(meeting_id=self.meeting.id, contact_id=self.guest_contact.id).first()
        self.assertIsNone(guest_entry.order_number)
        self.assertEqual(guest_entry.ticket.name, "Role-taker")

if __name__ == '__main__':
    unittest.main()
