
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
    SQLALCHEMY_ENGINE_OPTIONS = {}
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
        
        from app.models import Club
        self.club = Club(id=1, club_no='000000', club_name='Test Club')
        db.session.add(self.club)
        db.session.flush()
        
        self.officer_contact = Contact(Name="Test Officer", Type="Officer")
        self.member_contact = Contact(Name="Test Member", Type="Member")
        self.guest_contact = Contact(Name="Test Guest", Type="Guest")
        self.role = MeetingRole(name="Test Role", type="functionary", needs_approval=False, has_single_owner=False)
        
        from app.models import ContactClub
        cc_officer = ContactClub(contact=self.officer_contact, club_id=self.club.id, is_officer=True)
        cc_member = ContactClub(contact=self.member_contact, club_id=self.club.id, is_officer=False)
        cc_guest = ContactClub(contact=self.guest_contact, club_id=self.club.id, is_officer=False)
        
        db.session.add_all([self.officer_contact, self.member_contact, self.guest_contact, self.role, cc_officer, cc_member, cc_guest])
        
        # Seed Tickets
        from app.models import Ticket, Meeting
        tickets = [
            Ticket(name="Officer", type="Officer", price=0, club_id=self.club.id),
            Ticket(name="Early-bird", type="Member", price=0, club_id=self.club.id),
            Ticket(name="Role-taker", type="Guest", price=0, club_id=self.club.id),
            Ticket(name="Guest", type="Guest", price=0, club_id=self.club.id)
        ]
        db.session.add_all(tickets)
        
        from datetime import date
        self.meeting = Meeting(Meeting_Number=self.meeting_num, Meeting_Date=date(2025, 1, 1), club_id=self.club.id)
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
        self.assertIsNone(officer_entry.order_number)
        self.assertEqual(officer_entry.ticket.name, "Officer")

        # 2. Member Assignment
        Roster.sync_role_assignment(self.meeting.id, self.member_contact.id, self.role, 'assign')
        db.session.commit()
        
        member_entry = Roster.query.filter_by(meeting_id=self.meeting.id, contact_id=self.member_contact.id).first()
        self.assertIsNone(member_entry.order_number)
        self.assertEqual(member_entry.ticket.name, "Early-bird")

        # 3. Guest Assignment
        Roster.sync_role_assignment(self.meeting.id, self.guest_contact.id, self.role, 'assign')
        db.session.commit()
        
        guest_entry = Roster.query.filter_by(meeting_id=self.meeting.id, contact_id=self.guest_contact.id).first()
        self.assertIsNone(guest_entry.order_number)
        self.assertEqual(guest_entry.ticket.name, "Role-taker")

    def test_convert_expired_early_birds(self):
        """Verify that expired Early-bird tickets without order_number are converted to Walk-in tickets"""
        from app.models import Ticket, Roster
        from datetime import time
        
        # 1. Create a Walk-in ticket
        walk_in_ticket = Ticket.get_by_name(name="Walk-in", type="Guest", club_id=1)
        if not walk_in_ticket:
            walk_in_ticket = Ticket(name="Walk-in", type="Guest", price=40.0, club_id=1)
            db.session.add(walk_in_ticket)
            
        # 2. Get the Early-bird ticket and set its price and expired_at time
        early_bird_ticket = Ticket.get_by_name(name="Early-bird", type="Member", club_id=1)
        early_bird_ticket.price = 20.0
        early_bird_ticket.expired_at = time(12, 0)
        
        db.session.commit()
        
        # 3. Create Roster entries
        # Entry A: Early-bird ticket, order_number = None (Should be converted)
        entry_a = Roster(
            meeting_id=self.meeting.id,
            contact_id=self.member_contact.id,
            ticket_id=early_bird_ticket.id,
            order_number=None
        )
        # Entry B: Early-bird ticket, order_number = 123 (Should NOT be converted)
        entry_b = Roster(
            meeting_id=self.meeting.id,
            contact_id=self.officer_contact.id,
            ticket_id=early_bird_ticket.id,
            order_number=123
        )
        
        db.session.add_all([entry_a, entry_b])
        db.session.commit()
        
        # Verify initial prices are early-bird price (¥20.0)
        self.assertEqual(entry_a.amount, 20.0)
        self.assertEqual(entry_b.amount, 20.0)
        
        # 4. Trigger conversion
        Roster.convert_expired_early_birds(self.meeting.id)
        
        # Refresh from DB
        db.session.refresh(entry_a)
        db.session.refresh(entry_b)
        
        # 5. Assertions
        # Entry A should be converted to Walk-in ticket (price ¥40.0)
        self.assertEqual(entry_a.ticket_id, walk_in_ticket.id)
        self.assertEqual(entry_a.amount, 40.0)
        
        # Entry B should remain Early-bird (price ¥20.0)
        self.assertEqual(entry_b.ticket_id, early_bird_ticket.id)
        self.assertEqual(entry_b.amount, 20.0)

if __name__ == '__main__':
    unittest.main()
