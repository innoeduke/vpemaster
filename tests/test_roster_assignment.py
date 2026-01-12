
import unittest
import sys
import os

# Add project root to path ensuring 'app' can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Roster, Contact, Role
from config import Config
from sqlalchemy import func

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = True

class TestRosterAssignment(unittest.TestCase):
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
        
        self.role = Role(name="Test Role", type="functionary", needs_approval=False, is_distinct=False)
        
        db.session.add_all([self.officer_contact, self.member_contact, self.guest_contact, self.role])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_officer_assignment(self):
        """Test that officers get order number >= 1000 and Officer ticket"""
        Roster.sync_role_assignment(self.meeting_num, self.officer_contact.id, self.role, 'assign')
        db.session.commit()
        
        officer_entry = Roster.query.filter_by(meeting_number=self.meeting_num, contact_id=self.officer_contact.id).first()
        self.assertIsNotNone(officer_entry)
        self.assertGreaterEqual(officer_entry.order_number, 1000)
        self.assertEqual(officer_entry.ticket, "Officer")

    def test_multiple_officer_ordering(self):
        """Test that multiple officers get sequential order numbers"""
        officer2 = Contact(Name="Officer 2", Type="Officer")
        db.session.add(officer2)
        db.session.commit()

        Roster.sync_role_assignment(self.meeting_num, self.officer_contact.id, self.role, 'assign')
        Roster.sync_role_assignment(self.meeting_num, officer2.id, self.role, 'assign')
        db.session.commit()

        entry1 = Roster.query.filter_by(meeting_number=self.meeting_num, contact_id=self.officer_contact.id).first()
        entry2 = Roster.query.filter_by(meeting_number=self.meeting_num, contact_id=officer2.id).first()
        
        self.assertEqual(entry1.order_number, 1000)
        self.assertEqual(entry2.order_number, 1001)

    def test_member_assignment(self):
        """Test that members get None order number and Member ticket"""
        Roster.sync_role_assignment(self.meeting_num, self.member_contact.id, self.role, 'assign')
        db.session.commit()
        
        member_entry = Roster.query.filter_by(meeting_number=self.meeting_num, contact_id=self.member_contact.id).first()
        self.assertIsNotNone(member_entry)
        self.assertIsNone(member_entry.order_number)
        self.assertEqual(member_entry.ticket, "Member")

    def test_guest_assignment(self):
        """Test that guests get None order number and Role Taker ticket"""
        Roster.sync_role_assignment(self.meeting_num, self.guest_contact.id, self.role, 'assign')
        db.session.commit()
        
        guest_entry = Roster.query.filter_by(meeting_number=self.meeting_num, contact_id=self.guest_contact.id).first()
        self.assertIsNotNone(guest_entry)
        self.assertIsNone(guest_entry.order_number)
        self.assertEqual(guest_entry.ticket, "Role Taker")

if __name__ == '__main__':
    unittest.main()
