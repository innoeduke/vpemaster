import unittest
import sys
import os

# Add project root to path ensuring 'app' can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Contact, SessionType, Meeting, SessionLog
from app.models.roster import MeetingRole
from app.constants import SessionTypeID
from config import Config
from datetime import date, time
from unittest.mock import patch

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = True

class TestBookingDuplicates(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create basic data
        self.speaker_role = MeetingRole(name="Speaker", type="speech", needs_approval=False, is_distinct=True)
        self.timer_role = MeetingRole(name="Timer", type="role", needs_approval=False, is_distinct=False)
        db.session.add_all([self.speaker_role, self.timer_role])
        db.session.commit()

        self.speech_type = SessionType(Title="Prepared Speech", role_id=self.speaker_role.id)
        self.timer_type = SessionType(Title="Timer", role_id=self.timer_role.id)
        db.session.add_all([self.speech_type, self.timer_type])
        db.session.commit()

        # Create Club (required for Meeting)
        from app.models import Club
        self.club = Club(
            club_no='000000',
            club_name='Test Club',
            district='Test District'
        )
        db.session.add(self.club)
        db.session.commit()

        self.meeting = Meeting(
            Meeting_Number=123,
            Meeting_Date=date(2025, 1, 1),
            status='unpublished',  # Initially unpublished to allow setup
            club_id=self.club.id
        )
        db.session.add(self.meeting)
        db.session.commit()

        # Create user
        self.contact = Contact(Name="Test User", Email="test@example.com")
        db.session.add(self.contact)
        db.session.commit()
        
        self.user = User(username="testuser", email="test@example.com")
        self.user.set_password('password')
        db.session.add(self.user)
        db.session.commit()

        # Create sessions
        # Speaker 1
        self.sess1 = SessionLog(Meeting_Number=123, Type_ID=self.speech_type.id)
        # Speaker 2
        self.sess2 = SessionLog(Meeting_Number=123, Type_ID=self.speech_type.id)
        # Timer
        self.sess3 = SessionLog(Meeting_Number=123, Type_ID=self.timer_type.id)
        
        db.session.add_all([self.sess1, self.sess2, self.sess3])
        db.session.commit()
        
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    @patch('app.booking_routes.get_current_user_info')
    @patch('app.booking_routes.is_authorized')
    def test_duplicate_booking_prevention(self, mock_auth, mock_user_info):
        # Setup mocks
        mock_user_info.return_value = (self.user, self.contact.id)
        # Authorize everything for simplicity in this test
        mock_auth.return_value = True 

        # 1. User books Speaker 1
        with self.client:
            # Login not fully needed if we mock get_current_user_info and bypass login_required?
            # login_required decorators might be tricky. Let's try to mock login too or utilize mocks.
            # Actually, `login_required` checks flask_login.current_user.
            # We can mock `app.booking_routes.login_required`? No, it's imported.
            
            # Better: Login the user
            response = self.client.post('/login', data=dict(
                email='test@example.com',
                password='password'
            ), follow_redirects=True)
            
            # "Book" action logic test
            # Book first slot
            data = {'session_id': self.sess1.id, 'action': 'book'}
            resp = self.client.post('/booking/book', json=data)
            # if resp.status_code != 200:
            #     print(f"Book 1 failed: {resp.data}")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json['success'], True)
            
            # Verify owner
            s1 = db.session.get(SessionLog, self.sess1.id)
            self.assertEqual(s1.Owner_ID, self.contact.id)
            
            # 2. Attempt to book Speaker 2 (Duplicate Role)
            data = {'session_id': self.sess2.id, 'action': 'book'}
            resp = self.client.post('/booking/book', json=data)
            
            # This SHOULD fail after implementation
            # For TDD, this might pass (fail the test) initially if I don't implement the fix yet.
            # But I will implement code in same turn.
            
            # Expecting 200 OK now, but with success=False
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json['success'], False)
            self.assertIn("Warning: You have already booked", resp.json['message'])
            
            # Verify Speaker 2 is NOT booked
            s2 = db.session.get(SessionLog, self.sess2.id)
            self.assertIsNone(s2.Owner_ID)

    @patch('app.booking_routes.get_current_user_info')
    @patch('app.booking_routes.is_authorized')
    def test_different_role_booking(self, mock_auth, mock_user_info):
        mock_user_info.return_value = (self.user, self.contact.id)
        mock_auth.return_value = True
        
        with self.client:
            self.client.post('/login', data=dict(email='test@example.com', password='password'))
            
            # Book Speaker 1
            self.client.post('/booking/book', json={'session_id': self.sess1.id, 'action': 'book'})
            
            # Book Timer (Different Role)
            resp = self.client.post('/booking/book', json={'session_id': self.sess3.id, 'action': 'book'})
            
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json['success'], True)
            
            s3 = db.session.get(SessionLog, self.sess3.id)
            self.assertEqual(s3.Owner_ID, self.contact.id)

if __name__ == '__main__':
    unittest.main()
