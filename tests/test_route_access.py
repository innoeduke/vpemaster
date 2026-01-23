import unittest
import sys
import os
from datetime import datetime, date, time
from flask_login import current_user

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Meeting, User, Contact, Permission, AuthRole
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
        db.engine.dispose()
        self.app_context.pop()

    def populate_data(self):
        # Create Club first (required for Meeting and ContactClub)
        from app.models import Club, ContactClub, UserClub
        self.club = Club(
            club_no='000000',
            club_name='Test Club',
            district='Test District'
        )
        db.session.add(self.club)
        db.session.commit()

        # Create Users with different roles
        # Note: Role logic typically depends on Contact.Type or User.Role or User.is_officer property
        # Checking models.py would confirm how permissions are checked.
        # Based on previous output: user.is_officer checks contact type probably.
        
        # 1. Admin/Staff
        self.staff_contact = Contact(Name="Staff User", Type="Member")
        db.session.add(self.staff_contact)
        db.session.commit()
        
        # Link to club
        db.session.add(ContactClub(contact_id=self.staff_contact.id, club_id=self.club.id))
        db.session.commit()

        self.staff_user = User(
            username="staff",
            email="staff@test.com"
        )
        self.staff_user.set_password("password")
        db.session.add(self.staff_user)
        
        staff_role = AuthRole.query.filter_by(name='Staff').first()
        if not staff_role:
            # Create Staff role if it doesn't exist (for test environment)
            staff_role = AuthRole(name='Staff', description='Staff role', level=2)
            db.session.add(staff_role)
            db.session.flush()
        
        # Add AGENDA_VIEW and VOTING_VIEW_RESULTS permissions to Officer role
        from app.auth.permissions import Permissions
        agenda_view_perm = Permission.query.filter_by(name=Permissions.AGENDA_VIEW).first()
        if not agenda_view_perm:
            agenda_view_perm = Permission(name=Permissions.AGENDA_VIEW, description='View Agenda')
            db.session.add(agenda_view_perm)
        
        voting_results_perm = Permission.query.filter_by(name=Permissions.VOTING_VIEW_RESULTS).first()
        if not voting_results_perm:
            voting_results_perm = Permission(name=Permissions.VOTING_VIEW_RESULTS, description='View Voting Results')
            db.session.add(voting_results_perm)
        
        db.session.flush()

        if agenda_view_perm not in staff_role.permissions:
            staff_role.permissions.append(agenda_view_perm)
        if voting_results_perm not in staff_role.permissions:
            staff_role.permissions.append(voting_results_perm)
            
        self.staff_user.roles.append(staff_role)

        # Manually create UserClub for Staff
        db.session.add(UserClub(
            user_id=self.staff_user.id,
            club_id=self.club.id,
            club_role_level=staff_role.level,
            contact_id=self.staff_contact.id
        ))
        db.session.commit()
        
        # 2. User
        self.user_contact = Contact(Name="Standard User", Type="Member")
        db.session.add(self.user_contact)
        db.session.commit()
        
        # Link to club
        db.session.add(ContactClub(contact_id=self.user_contact.id, club_id=self.club.id))
        db.session.commit()
        
        self.user_user = User(
            username="user",
            email="user@test.com"
        )
        self.user_user.set_password("password")
        db.session.add(self.user_user)

        user_role = AuthRole.query.filter_by(name='User').first()
        if not user_role:
            user_role = AuthRole(name='User', description='User role', level=1)
            db.session.add(user_role)
            db.session.flush()
        
        # Add AGENDA_VIEW permission to User role
        if agenda_view_perm not in user_role.permissions:
            user_role.permissions.append(agenda_view_perm)
            
        self.user_user.roles.append(user_role)
        
        # Manually create UserClub for User
        db.session.add(UserClub(
            user_id=self.user_user.id,
            club_id=self.club.id,
            club_role_level=user_role.level,
            contact_id=self.user_contact.id
        ))
        db.session.commit()

        # 3. Guest (No user needed, just unauth)

        # Create Meetings with different statuses
        today = date.today()
        
        self.m_unpublished = Meeting(Meeting_Number=100, Meeting_Date=today, status='unpublished', club_id=self.club.id)
        self.m_not_started = Meeting(Meeting_Number=101, Meeting_Date=today, status='not started', club_id=self.club.id)
        self.m_running = Meeting(Meeting_Number=102, Meeting_Date=today, status='running', club_id=self.club.id)
        self.m_finished = Meeting(Meeting_Number=103, Meeting_Date=today, status='finished', club_id=self.club.id)
        
        db.session.add_all([self.m_unpublished, self.m_not_started, self.m_running, self.m_finished])
        db.session.commit()
        
        # Add Guest Role Logic for AnonymousUser
        guest_role = AuthRole.query.filter_by(name='Guest').first()
        if not guest_role:
            guest_role = AuthRole(name='Guest', description='Guest role', level=0)
            db.session.add(guest_role)
            db.session.flush()
        
        # Assign AGENDA_VIEW and ABOUT_CLUB_VIEW to Guest (Required for Authorized Club Context)
        if agenda_view_perm not in guest_role.permissions:
            guest_role.permissions.append(agenda_view_perm)
            
        about_club_perm = Permission.query.filter_by(name=Permissions.ABOUT_CLUB_VIEW).first()
        if not about_club_perm:
             about_club_perm = Permission(name=Permissions.ABOUT_CLUB_VIEW, description='View Club Info')
             db.session.add(about_club_perm)
             db.session.flush()

        if about_club_perm not in guest_role.permissions:
            guest_role.permissions.append(about_club_perm)
            
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
        # 1. Unpublished Meeting -> Redirect to meeting-notice page
        response = self.client.get(f'/agenda?meeting_number={self.m_unpublished.Meeting_Number}')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/meeting-notice', response.location)
        
        # Booking Unpublished -> Redirect to Login (@login_required)
        response = self.client.get(f'/booking/{self.m_unpublished.Meeting_Number}')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.location)
        
        # Voting Unpublished -> Redirect to meeting-notice
        response = self.client.get(f'/voting/{self.m_unpublished.Meeting_Number}')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/meeting-notice', response.location)

    def test_user_access(self):
        self.login('user@test.com', 'password')
        
        # Member vs Unpublished -> Redirect to meeting-notice
        response = self.client.get(f'/agenda?meeting_number={self.m_unpublished.Meeting_Number}')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/meeting-notice', response.location)

        # Member vs Not Started -> 200
        response = self.client.get(f'/agenda?meeting_number={self.m_not_started.Meeting_Number}')
        self.assertEqual(response.status_code, 200, "User accessing not started agenda should be 200")
        
        # Member vs Running -> 200
        response = self.client.get(f'/agenda?meeting_number={self.m_running.Meeting_Number}')
        self.assertEqual(response.status_code, 200, "User accessing running agenda should be 200")
        
        self.logout()

    def test_staff_access(self):
        self.login('staff@test.com', 'password')
        
        # Staff vs Unpublished -> 200
        response = self.client.get(f'/agenda?meeting_number={self.m_unpublished.Meeting_Number}')
        self.assertEqual(response.status_code, 200, "Staff accessing unpublished agenda should be 200")
        
        response = self.client.get(f'/booking/{self.m_unpublished.Meeting_Number}')
        self.assertEqual(response.status_code, 200)
        
        # Voting Unpublished -> Staff (Redirect 302)
        response = self.client.get(f'/voting/{self.m_unpublished.Meeting_Number}')
        self.assertEqual(response.status_code, 302)
        
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
