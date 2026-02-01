import sys
import os
import unittest
from flask import session

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Club, Contact, UserClub, AuthRole, Permission
from app.auth.permissions import Permissions
from app.club_context import get_or_set_default_club, set_current_club_id
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class TestClubContextSwitch(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        
        # Create Clubs
        self.club_a = Club(club_name="Club A", club_no="111111")
        self.club_b = Club(club_name="Club B", club_no="222222")
        db.session.add_all([self.club_a, self.club_b])
        db.session.commit()
        
        # Create Users
        # User A: Member of Club A only
        self.user_a = self.create_user("user_a", self.club_a)
        # User B: Member of Club B only
        self.user_b = self.create_user("user_b", self.club_b)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def create_user(self, username, club):
        c = Contact(Name=username, Email=f"{username}@example.com", Type='Member')
        db.session.add(c)
        db.session.flush()
        
        u = User(username=username, email=f"{username}@example.com", status='active')
        u.set_password('password')
        db.session.add(u)
        db.session.flush()
        
        uc = UserClub(user_id=u.id, club_id=club.id, contact_id=c.id, is_home=True, club_role_level=1)
        db.session.add(uc)
        db.session.commit()
        return u

    def test_session_validation(self):
        # 1. Login as User A
        self.client.post('/login', data={'username': 'user_a', 'password': 'password'})
        
        with self.client.session_transaction() as sess:
            # Simulate setting context to Club A
            sess['current_club_id'] = self.club_a.id
            
        # Verify get_or_set_default_club respects it
        with self.client:
            self.client.get('/') # Trigger request context
            club_id = get_or_set_default_club()
            self.assertEqual(club_id, self.club_a.id)

        # 2. Logout
        self.client.get('/logout')
        
        # 3. Validation: Session should NOT have current_club_id
        # (Though in test client cookie handling might be tricky, let's check validation logic directly next)
        
        # 4. Login as User B
        self.client.post('/login', data={'username': 'user_b', 'password': 'password'})
        
        # FORCE BAD STATE: Inject Club A into session for User B (who is NOT a member of Club A)
        with self.client.session_transaction() as sess:
             sess['current_club_id'] = self.club_a.id
             
        # 5. Verify get_or_set_default_club REJECTS Club A and switches to Club B/Default
        with self.client:
            self.client.get('/') # Trigger request
            club_id = get_or_set_default_club()
            
            # Should NOT be Club A
            self.assertNotEqual(club_id, self.club_a.id)
            # Should be Club B (since it's user_b's home/only club)
            self.assertEqual(club_id, self.club_b.id)
            
            print(f"Correctly switched from invalid {self.club_a.id} to valid {club_id}")

if __name__ == '__main__':
    unittest.main()
