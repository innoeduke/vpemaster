
import unittest
from app import create_app, db
from app.models import SessionLog, SessionType, Contact, Meeting, Waitlist, Roster
from app.models.roster import MeetingRole
from app.services.role_service import RoleService
from config import Config
from datetime import date

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class TestMultiOwner(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create Club
        from app.models import Club
        self.club = Club(club_no='000000', club_name='Test Club')
        db.session.add(self.club)
        db.session.commit()

        # Create Meeting
        self.meeting = Meeting(Meeting_Number=1, Meeting_Date=date.today(), status='running', club_id=self.club.id)
        db.session.add(self.meeting)
        
        # Create Contacts
        self.contact1 = Contact(Name="Alice", Email="alice@example.com")
        self.contact2 = Contact(Name="Bob", Email="bob@example.com")
        self.contact3 = Contact(Name="Charlie", Email="charlie@example.com")
        db.session.add_all([self.contact1, self.contact2, self.contact3])
        
        # Create Role
        self.role = MeetingRole(name="Speaker", type="speech", needs_approval=False, is_distinct=False)
        db.session.add(self.role)
        db.session.commit()
        
        # Create Session Type
        self.stype = SessionType(role_id=self.role.id, Title="Prepared Speech")
        db.session.add(self.stype)
        db.session.commit()
        
        # Create Log
        self.log = SessionLog(Meeting_Number=1, Type_ID=self.stype.id)
        db.session.add(self.log)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_assign_multiple_owners(self):
        """Test assigning multiple owners via RoleService."""
        owners = [self.contact1.id, self.contact2.id]
        RoleService.assign_meeting_role(self.log, owners)
        db.session.commit()
        
        # Verify
        self.assertEqual(len(self.log.owners), 2)
        owner_names = [c.Name for c in self.log.owners]
        self.assertIn("Alice", owner_names)
        self.assertIn("Bob", owner_names)
        
        # Verify Primary Owner
        self.assertEqual(self.log.Owner_ID, self.contact1.id)
        self.assertEqual(self.log.owner, self.contact1)

    def test_filter_by_secondary_owner(self):
        """Test querying log by secondary owner."""
        RoleService.assign_meeting_role(self.log, [self.contact1.id, self.contact2.id])
        db.session.commit()
        
        # Query using the new method (simulated)
        # In speech_logs_routes: base_query.filter(SessionLog.owners.any(id=filters['speaker_id']))
        results = SessionLog.query.filter(SessionLog.owners.any(id=self.contact2.id)).all()
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].id, self.log.id)

    def test_change_owners(self):
        """Test changing owners replaces correctly."""
        # Start with Alice & Bob
        RoleService.assign_meeting_role(self.log, [self.contact1.id, self.contact2.id])
        db.session.commit()
        
        # Change to Bob & Charlie
        RoleService.assign_meeting_role(self.log, [self.contact2.id, self.contact3.id])
        db.session.commit()
        
        self.assertEqual(len(self.log.owners), 2)
        owner_ids = [c.id for c in self.log.owners]
        self.assertIn(self.contact2.id, owner_ids)
        self.assertIn(self.contact3.id, owner_ids)
        self.assertNotIn(self.contact1.id, owner_ids)
        
        # Check Primary (should be Bob now as he is first in list passed or first in sorted?)
        # Logic in set_owners preserves order of passed IDs if possible, or sorts by DB retreival if not careful.
        # My implementation: 
        # owner_contacts = Contact.query.filter(Contact.id.in_(new_owner_ids)).all()
        # owner_contacts.sort(key=lambda c: new_owner_ids.index(c.id))
        
        self.assertEqual(self.log.Owner_ID, self.contact2.id)

if __name__ == '__main__':
    unittest.main()
