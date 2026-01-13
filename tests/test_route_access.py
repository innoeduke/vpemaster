import unittest
import sys
import os
from datetime import datetime, date, time
from flask_login import current_user

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Meeting, User, Contact
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SERVER_NAME = 'localhost.localdomain' # Needed for url_for in some cases

class RouteAccessTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.client = self.app.test_client()
        self.populate_data()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def populate_data(self):
        # Create Users with different roles
        # Note: Role logic typically depends on Contact.Type or User.Role or User.is_officer property
        # Checking models.py would confirm how permissions are checked.
        # Based on previous output: user.is_officer checks contact type probably.
        
        # 1. Admin/Officer
        self.officer_contact = Contact(Name="Officer User", Type="Member", Club="Test Club")
        db.session.add(self.officer_contact)
        db.session.commit()

        self.officer_user = User(
            Username="officer",
            Email="officer@test.com", 
            Contact_ID=self.officer_contact.id,
            Role="Officer"
        )
        self.officer_user.set_password("password")
        db.session.add(self.officer_user)
        
        # 2. Member
        self.member_contact = Contact(Name="Member User", Type="Member", Club="Test Club")
        db.session.add(self.member_contact)
        db.session.commit()
        self.member_user = User(
            Username="member",
            Email="member@test.com", 
            Contact_ID=self.member_contact.id,
            Role="Member"
        )
        self.member_user.set_password("password")
        db.session.add(self.member_user)

        # 3. Guest (No user needed, just unauth)

        # Create Meetings with different statuses
        today = date.today()
        
        self.m_unpublished = Meeting(Meeting_Number=100, Meeting_Date=today, status='unpublished')
        self.m_not_started = Meeting(Meeting_Number=101, Meeting_Date=today, status='not started')
        self.m_running = Meeting(Meeting_Number=102, Meeting_Date=today, status='running')
        self.m_finished = Meeting(Meeting_Number=103, Meeting_Date=today, status='finished')
        
        db.session.add_all([self.m_unpublished, self.m_not_started, self.m_running, self.m_finished])
        db.session.commit()

    def login(self, email, password):
        return self.client.post('/login', data=dict(
            username=email,
            password=password
        ), follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    # --- TESTS ---

    def test_guest_access(self):
        # 1. Unpublished Meeting -> Should be 403 Forbidden
        response = self.client.get(f'/agenda?meeting_number={self.m_unpublished.Meeting_Number}')
        self.assertEqual(response.status_code, 403, "Guest accessing unpublished agenda should be 403")
        
        # 2. Not Started -> Should be 403 Forbidden (New Restriction)
        response = self.client.get(f'/agenda?meeting_number={self.m_not_started.Meeting_Number}')
        self.assertEqual(response.status_code, 403, "Guest accessing not started agenda should be 403")
        
        # 3. Running -> 200 OK
        response = self.client.get(f'/agenda?meeting_number={self.m_running.Meeting_Number}')
        self.assertEqual(response.status_code, 200, "Guest accessing running agenda should be 200")

        # 4. Finished -> Should be 403 Forbidden (New Restriction)
        response = self.client.get(f'/agenda?meeting_number={self.m_finished.Meeting_Number}')
        self.assertEqual(response.status_code, 403, "Guest accessing finished agenda should be 403")

        # Booking / Voting / Roster checks
        
        # Booking Unpublished
        response = self.client.get(f'/booking/{self.m_unpublished.Meeting_Number}')
        self.assertEqual(response.status_code, 403)
        
        # Voting Unpublished
        response = self.client.get(f'/voting/{self.m_unpublished.Meeting_Number}')
        self.assertEqual(response.status_code, 403)

    def test_member_access(self):
        self.login('member@test.com', 'password')
        
        # Member vs Unpublished -> 403 (unless manager)
        response = self.client.get(f'/agenda?meeting_number={self.m_unpublished.Meeting_Number}')
        self.assertEqual(response.status_code, 403, "Member accessing unpublished agenda should be 403")

        # Member vs Not Started -> 200
        response = self.client.get(f'/agenda?meeting_number={self.m_not_started.Meeting_Number}')
        self.assertEqual(response.status_code, 200, "Member accessing not started agenda should be 200")
        
        # Member vs Running -> 200
        response = self.client.get(f'/agenda?meeting_number={self.m_running.Meeting_Number}')
        self.assertEqual(response.status_code, 200, "Member accessing running agenda should be 200")
        
        self.logout()

    def test_officer_access(self):
        self.login('officer@test.com', 'password')
        
        # Officer vs Unpublished -> 200
        response = self.client.get(f'/agenda?meeting_number={self.m_unpublished.Meeting_Number}')
        self.assertEqual(response.status_code, 200, "Officer accessing unpublished agenda should be 200")
        
        response = self.client.get(f'/booking/{self.m_unpublished.Meeting_Number}')
        self.assertEqual(response.status_code, 200)
        
        response = self.client.get(f'/voting/{self.m_unpublished.Meeting_Number}')
        self.assertEqual(response.status_code, 200)
        
        self.logout()

    def test_missing_params(self):
        # Guest hitting /agenda with no params -> Should default to something valid (not started)
        # Verify it doesn't crash or return 403 (due to default unpublished pick)
        response = self.client.get('/agenda')
        
        self.assertEqual(response.status_code, 200, "Guest default agenda load should be 200")
        # Should default to the running meeting (102) if one exists
        self.assertIn(b'Meeting 102', response.data)

if __name__ == '__main__':
    unittest.main()
