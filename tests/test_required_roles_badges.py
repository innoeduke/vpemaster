import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Contact, SessionType, Meeting, SessionLog, LevelRole
from app.models.roster import MeetingRole
from config import Config
from datetime import date

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = True

class TestRequiredRolesBadges(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create Role
        self.role = MeetingRole(name="Ah-Counter", type="role", needs_approval=False, has_single_owner=True)
        db.session.add(self.role)
        db.session.commit()

        # Create Level Requirement
        self.req = LevelRole(level=1, role="Ah-Counter", type="required", count_required=1)
        db.session.add(self.req)
        db.session.commit()

        # Create Member who needs it
        self.member = Contact(Name="Member One", Type="Member", Current_Path="Dynamic Leadership")
        db.session.add(self.member)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_contact_role_requirements(self):
        from app.booking_routes import _get_contact_role_requirements
        req_map, _, _ = _get_contact_role_requirements(self.member, 1) # club_id=1
        
        self.assertIn('ahcounter', req_map)
        self.assertEqual(req_map['ahcounter'], 1)

if __name__ == '__main__':
    unittest.main()
