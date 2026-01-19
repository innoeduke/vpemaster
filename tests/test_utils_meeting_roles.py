
import unittest
from app import create_app, db
from app.models import Contact, Meeting, SessionLog, SessionType, MeetingRole, Roster, Ticket
from app.utils import get_meeting_roles
from datetime import date, datetime, timezone
from flask import g

class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SECRET_KEY = 'test'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False
    CACHE_TYPE = 'SimpleCache'

class TestMeetingRolesHelper(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Setup Data
        self.role_tm = MeetingRole(name='Toastmaster', type='standard', needs_approval=False, is_distinct=False)
        self.role_sp1 = MeetingRole(name='Speaker', type='standard', needs_approval=False, is_distinct=True)
        db.session.add_all([self.role_tm, self.role_sp1])
        db.session.commit()
        
        self.st_tm = SessionType(Title='Toastmaster', role_id=self.role_tm.id)
        self.st_sp1 = SessionType(Title='Speaker 1', role_id=self.role_sp1.id)
        db.session.add_all([self.st_tm, self.st_sp1])
        db.session.commit()

        self.contact1 = Contact(Name='User One', Email='user1@example.com', Type='Member')
        self.contact2 = Contact(Name='User Two', Email='user2@example.com', Type='Member')
        db.session.add_all([self.contact1, self.contact2])
        db.session.commit()

        self.meeting = Meeting(Meeting_Number=100, Meeting_Date=date(2025, 1, 1), status='not started', club_id=1)
        db.session.add(self.meeting)
        db.session.commit()
        
        # Create Logs
        # Contact 1 is Toastmaster
        self.log1 = SessionLog(
            Meeting_Number=100, 
            Type_ID=self.st_tm.id,
            Owner_ID=self.contact1.id
        )
        
        # Contact 1 is ALSO Speaker (Multi-role test)
        self.log2 = SessionLog(
            Meeting_Number=100, 
            Type_ID=self.st_sp1.id, 
            Owner_ID=self.contact1.id,
            Session_Title='Speech 1'
        )
        
        db.session.add_all([self.log1, self.log2])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_get_meeting_roles_basic(self):
        """Test fetching roles for a contact"""
        roles_map = get_meeting_roles(meeting_number=100)
        roles = roles_map.get(str(self.contact1.id), [])
        self.assertEqual(len(roles), 2)
        names = sorted([r['name'] for r in roles])
        self.assertEqual(names, ['Speaker', 'Toastmaster'])

    def test_get_meeting_roles_cache(self):
        """Test that caching works via Flask-Caching"""
        from app import cache
        
        # First call populates cache
        roles_map1 = get_meeting_roles(club_id=1, meeting_number=100)
        
        cache_key = "meeting_roles_1_100"
        
        # Verify cache entry exists
        self.assertIsNotNone(cache.get(cache_key))
        
        # Tamper
        fake_roles = cache.get(cache_key)
        fake_roles[str(self.contact1.id)] = [] # Clear them
        cache.set(cache_key, fake_roles)
        
        # Second call should return empty from cache
        roles_map2 = get_meeting_roles(club_id=1, meeting_number=100)
        roles2 = roles_map2.get(str(self.contact1.id), [])
        self.assertEqual(roles2, [])

    def test_get_meeting_roles_all(self):
        """Test fetching all roles mapping"""
        roles_map = get_meeting_roles(club_id=1, meeting_number=100)
        self.assertIn(str(self.contact1.id), roles_map)
        self.assertEqual(len(roles_map[str(self.contact1.id)]), 2)
        self.assertNotIn(str(self.contact2.id), roles_map)

if __name__ == '__main__':
    unittest.main()
