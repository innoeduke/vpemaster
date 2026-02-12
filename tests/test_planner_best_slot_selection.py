import unittest
from unittest.mock import patch
from app import create_app, db
from app.models import Meeting, Club, User
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SERVER_NAME = 'localhost'

class TestPlannerSlotSelection(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create Club
        self.club = Club(club_no='000000', club_name='Test Club', district='Test District')
        db.session.add(self.club)
        db.session.commit()

        # Create Meeting
        self.meeting = Meeting(Meeting_Number=1, status='unpublished', club_id=self.club.id)
        db.session.add(self.meeting)
        
        # Create User
        self.user = User(username='testuser', email='test@example.com', password_hash='dummy')
        db.session.add(self.user)
        db.session.commit()

        self.client = self.app.test_client()
        
        # Mock login
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(self.user.id)
            sess['current_club_id'] = self.club.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('app.services.role_service.RoleService.get_meeting_roles')
    def test_best_slot_selection(self, mock_get_roles):
        # Mock role data
        # Role 1 (Speaker) has 3 slots:
        # Slot 1: Owner=101, WL=[] (Score 1)
        # Slot 2: Owner=None, WL=[102, 103] (Score 2)
        # Slot 3: Owner=None, WL=[] (Score 0) -> BEST
        
        mock_get_roles.return_value = [
            {
                'role': 'Speaker',
                'role_id': 1,
                'owner_id': 101,
                'session_id': 10,
                'has_single_owner': True,
                'waitlist': []
            },
            {
                'role': 'Speaker',
                'role_id': 1,
                'owner_id': None,
                'session_id': 11,
                'has_single_owner': True,
                'waitlist': [{'id': 102}, {'id': 103}]
            },
            {
                'role': 'Speaker',
                'role_id': 1,
                'owner_id': None,
                'session_id': 12,
                'has_single_owner': True,
                'waitlist': []
            }
        ]
        
        response = self.client.get('/api/meeting/1')
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        
        # Should pick session_id 12
        roles = data['roles']
        speaker_role = next(r for r in roles if r['id'] == 1)
        self.assertEqual(speaker_role['session_id'], 12)
        self.assertTrue(speaker_role['is_available'])

    @patch('app.services.role_service.RoleService.get_meeting_roles')
    def test_tie_breaker_no_owner(self, mock_get_roles):
        # Tie-breaker: Same score, pick the one without owner
        # Slot 1: Owner=101, WL=[] (Score 1, is_available=False)
        # Slot 2: Owner=None, WL=[102] (Score 1, is_available=True) -> BEST
        
        mock_get_roles.return_value = [
            {
                'role': 'Speaker',
                'role_id': 1,
                'owner_id': 101,
                'session_id': 10,
                'has_single_owner': True,
                'waitlist': []
            },
            {
                'role': 'Speaker',
                'role_id': 1,
                'owner_id': None,
                'session_id': 11,
                'has_single_owner': True,
                'waitlist': [{'id': 102}]
            }
        ]
        
        response = self.client.get('/api/meeting/1')
        data = response.get_json()
        
        roles = data['roles']
        speaker_role = next(r for r in roles if r['id'] == 1)
        self.assertEqual(speaker_role['session_id'], 11)
        self.assertTrue(speaker_role['is_available'])

    @patch('app.services.role_service.RoleService.get_meeting_roles')
    def test_shared_role_ignored(self, mock_get_roles):
        # Roles with has_single_owner=False should not be optimized
        
        mock_get_roles.return_value = [
            {
                'role': 'Shared Role',
                'role_id': 2,
                'owner_id': 101,
                'session_id': 20,
                'has_single_owner': False,
                'waitlist': []
            },
            {
                'role': 'Shared Role',
                'role_id': 2,
                'owner_id': None,
                'session_id': 21,
                'has_single_owner': False,
                'waitlist': []
            }
        ]
        
        response = self.client.get('/api/meeting/1')
        data = response.get_json()
        
        roles = data['roles']
        shared_role = next(r for r in roles if r['id'] == 2)
        # The first one seen should remain
        self.assertEqual(shared_role['session_id'], 20)

if __name__ == '__main__':
    unittest.main()
