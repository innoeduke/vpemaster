import unittest
from datetime import datetime, date
from app import create_app, db
from app.models import SessionLog, SessionType, Role, Contact, Meeting, Waitlist, Roster
from app.services.role_service import RoleService
from app.constants import SessionTypeID
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class TestRoleService(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create Basic Data
        self.meeting = Meeting(Meeting_Number=1, Meeting_Date=date.today(), status='running')
        db.session.add(self.meeting)
        
        self.contact1 = Contact(Name="Alice", Email="alice@example.com")
        self.contact2 = Contact(Name="Bob", Email="bob@example.com")
        db.session.add_all([self.contact1, self.contact2])
        
        # Create Role: Toastmaster (Distinct, No Approval)
        self.role_tm = Role(name="Toastmaster", type="meeting", needs_approval=False, is_distinct=True, is_member_only=False)
        db.session.add(self.role_tm)

        # Create Role: Speaker (Not Distinct, Needs Approval for test)
        self.role_spk = Role(name="Speaker", type="meeting", needs_approval=True, is_distinct=False, is_member_only=True)
        db.session.add(self.role_spk)
        
        db.session.commit()
        
        # Refresh IDs
        self.tm_type = SessionType(role_id=self.role_tm.id, Title="Toastmaster Type")
        self.spk_type = SessionType(role_id=self.role_spk.id, Title="Speaker Type")
        db.session.add_all([self.tm_type, self.spk_type])
        db.session.commit()

        # Create Sessions
        self.log_tm = SessionLog(Meeting_Number=1, Type_ID=self.tm_type.id)
        self.log_spk1 = SessionLog(Meeting_Number=1, Type_ID=self.spk_type.id)
        self.log_spk2 = SessionLog(Meeting_Number=1, Type_ID=self.spk_type.id)
        db.session.add_all([self.log_tm, self.log_spk1, self.log_spk2])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def test_book_distinct_role(self):
        """Test booking a distinct role that doesn't need approval."""
        success, msg = RoleService.book_meeting_role(self.log_tm, self.contact1.id)
        self.assertTrue(success)
        self.assertEqual(self.log_tm.Owner_ID, self.contact1.id)
        
        # Check Roster Sync
        roster_entry = Roster.query.filter_by(meeting_number=1, contact_id=self.contact1.id).first()
        self.assertIsNotNone(roster_entry)
        self.assertTrue(roster_entry.has_role(self.role_tm))

    def test_book_duplicate_role_prevention(self):
        """Test preventing booking same role type twice."""
        # 1. Book first speaker slot
        # Mock approval requirement away for this test or manually assign
        self.role_spk.needs_approval = False
        db.session.commit()
        
        success, msg = RoleService.book_meeting_role(self.log_spk1, self.contact1.id)
        self.assertTrue(success)

        # 2. Try booking second speaker slot
        success, msg = RoleService.book_meeting_role(self.log_spk2, self.contact1.id)
        self.assertFalse(success)
        self.assertIn("already booked a role of this type", msg)

    def test_waitlist_logic(self):
        """Test waitlist joining and approval."""
        # Role needs approval
        self.assertTrue(self.role_spk.needs_approval)
        
        # 1. Join Waitlist
        success, msg = RoleService.book_meeting_role(self.log_spk1, self.contact1.id)
        self.assertTrue(success)
        self.assertIn("waitlist", msg)
        
        wl = Waitlist.query.filter_by(session_log_id=self.log_spk1.id, contact_id=self.contact1.id).first()
        self.assertIsNotNone(wl)
        
        # 2. Approve Waitlist
        success, msg = RoleService.approve_waitlist(self.log_spk1)
        self.assertTrue(success)
        
        # Verify assignment
        self.assertEqual(self.log_spk1.Owner_ID, self.contact1.id)
        
        # Verify waitlist cleared for THIS group of roles?
        # RoleService.approve_waitlist calls assign_meeting_role -> set_owner -> clears waitlists
        wl_after = Waitlist.query.filter_by(session_log_id=self.log_spk1.id, contact_id=self.contact1.id).first()
        self.assertIsNone(wl_after)

    def test_cancel_role_auto_promote(self):
        """Test cancellation and auto-promotion from waitlist."""
        # Setup: Contact1 owns, Contact2 on waitlist
        self.role_tm.needs_approval = False # No approval for TM
        RoleService.book_meeting_role(self.log_tm, self.contact1.id)
        
        # Add Contact2 to waitlist manually (since book would fail as taken)
        RoleService.join_waitlist(self.log_tm, self.contact2.id)
        
        # Cancel Owner
        success, msg = RoleService.cancel_meeting_role(self.log_tm, self.contact1.id)
        self.assertTrue(success)
        
        # Verify Contact2 is now owner
        self.assertEqual(self.log_tm.Owner_ID, self.contact2.id)
        
        # Verify Roster updated
        roster1 = Roster.query.filter_by(meeting_number=1, contact_id=self.contact1.id).first()
        roster2 = Roster.query.filter_by(meeting_number=1, contact_id=self.contact2.id).first()
        
        # Depending on implementation, roster entry might remain but role removed
        if roster1:
             self.assertFalse(roster1.has_role(self.role_tm))
             
        self.assertIsNotNone(roster2)
        self.assertTrue(roster2.has_role(self.role_tm))

if __name__ == '__main__':
    unittest.main()
