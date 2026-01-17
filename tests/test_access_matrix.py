
import unittest
import sys
import os
from datetime import date
from flask_login import login_user, logout_user

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Contact, AuthRole, Meeting, Permission, UserClub
from app.auth.permissions import Permissions
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class AccessMatrixTestCase(unittest.TestCase):
    # Class-level constants to avoid redundancy
    ALL_ROLES = ['guest', 'user', 'staff', 'clubadmin', 'sysadmin']
    ALL_STATUSES = ['unpublished', 'not started', 'running', 'finished']
    ADMIN_RESOURCES = ['/settings', '/users']
    PUBLIC_RESOURCES = ['/pathway_library', '/lucky_draw/', '/roster/', '/contacts', '/speech_logs']
    
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.client = self.app.test_client()
        self.populate_data()
        
        # Cache role permissions for test logic
        self.role_permissions_map = {}
        for role_name in ['SysAdmin', 'ClubAdmin', 'Staff', 'User']:
            u = User.query.filter_by(username=role_name.lower()).first()
            self.role_permissions_map[role_name.lower()] = u.get_permissions()
            
        # Refactored: Fetch Guest permissions from DB
        guest_role = AuthRole.query.filter_by(name='Guest').first()
        self.role_permissions_map['guest'] = set(p.name for p in guest_role.permissions) if guest_role else set()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def populate_data(self):
        # Create Roles
        self.roles = {}
        # Added Guest Role (Level 0)
        for name, level in [('SysAdmin', 10), ('ClubAdmin', 5), ('Staff', 2), ('User', 1), ('Guest', 0)]:
            role = AuthRole(name=name, description=f"{name} Role", level=level)
            db.session.add(role)
            self.roles[name] = role
        
        # Create Users
        self.users = {}
        # Create Club (required for Meeting and UserClub)
        from app.models import Club
        self.club = Club(
            club_no='000000',
            club_name='Test Club',
            district='Test District'
        )
        db.session.add(self.club)
        db.session.flush()

        for role_name in ['SysAdmin', 'ClubAdmin', 'Staff', 'User']:
            contact = Contact(Name=f"{role_name} User", Type="Member")
            db.session.add(contact)
            db.session.flush()
            
            user = User(
                username=role_name.lower(),
                email=f"{role_name.lower()}@test.com",
                contact_id=contact.id
            )
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            
            # Use UserClub to link role to user and club
            uc = UserClub(user_id=user.id, club_id=self.club.id, club_role_id=self.roles[role_name].id, contact_id=contact.id)
            db.session.add(uc)
            self.users[role_name.lower()] = user

        # Define Permissions
        all_perms_map = {
            'SysAdmin': [
                Permissions.AGENDA_VIEW, Permissions.AGENDA_EDIT,
                Permissions.BOOKING_BOOK_OWN, Permissions.BOOKING_ASSIGN_ALL,
                Permissions.SETTINGS_VIEW_ALL, Permissions.ROSTER_VIEW, Permissions.ROSTER_EDIT,
                Permissions.CONTACT_BOOK_VIEW, Permissions.CONTACT_BOOK_EDIT,
                Permissions.SPEECH_LOGS_VIEW_ALL, Permissions.VOTING_VIEW_RESULTS,
                Permissions.VOTING_TRACK_PROGRESS, Permissions.LUCKY_DRAW_VIEW, Permissions.LUCKY_DRAW_EDIT,
                Permissions.PATHWAY_LIB_EDIT, Permissions.PATHWAY_LIB_VIEW
            ],
            'ClubAdmin': [
                Permissions.AGENDA_VIEW, Permissions.BOOKING_ASSIGN_ALL, 
                Permissions.SETTINGS_VIEW_ALL, Permissions.ROSTER_VIEW, Permissions.ROSTER_EDIT,
                Permissions.CONTACT_BOOK_VIEW, Permissions.SPEECH_LOGS_VIEW_ALL,
                Permissions.VOTING_VIEW_RESULTS, Permissions.VOTING_TRACK_PROGRESS,
                Permissions.LUCKY_DRAW_VIEW, Permissions.LUCKY_DRAW_EDIT,
                Permissions.PATHWAY_LIB_EDIT, Permissions.PATHWAY_LIB_VIEW
            ],
            'Staff': [
                Permissions.AGENDA_VIEW, Permissions.ROSTER_VIEW, 
                Permissions.CONTACT_BOOK_VIEW, Permissions.SPEECH_LOGS_VIEW_ALL,
                Permissions.VOTING_VIEW_RESULTS, Permissions.LUCKY_DRAW_VIEW, 
                Permissions.PATHWAY_LIB_VIEW
            ],
            'User': [
                Permissions.AGENDA_VIEW, Permissions.BOOKING_BOOK_OWN, Permissions.PATHWAY_LIB_VIEW
            ],
            'Guest': [
                Permissions.AGENDA_VIEW, Permissions.PATHWAY_LIB_VIEW
            ]
        }
        
        # Create Permission Objects
        perm_objs = {}
        unique_perms = set()
        for p_list in all_perms_map.values():
            unique_perms.update(p_list)
            
        for p_name in unique_perms:
            p = Permission(name=p_name, description=p_name)
            db.session.add(p)
            perm_objs[p_name] = p
            
        db.session.flush()

        # Assign to Roles
        for role_name, p_names in all_perms_map.items():
            role = self.roles[role_name]
            for p_name in p_names:
                role.permissions.append(perm_objs[p_name])

        db.session.commit()

        # Create Meetings
        today = date.today()
        self.meetings = {}
        statuses = ['unpublished', 'not started', 'running', 'finished']
        for idx, status in enumerate(statuses):
            m_num = 100 + idx
            meeting = Meeting(
                Meeting_Number=m_num, 
                Meeting_Date=today, 
                status=status,
                club_id=self.club.id
            )
            db.session.add(meeting)
            self.meetings[status] = meeting
            
        db.session.commit()

    def login(self, username):
        return self.client.post('/login', data=dict(
            username=f"{username}@test.com",
            password="password"
        ), follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_role_definitions(self):
        """Verify that roles have the expected permissions."""
        admin_perms = self.role_permissions_map['sysadmin']
        self.assertIn(Permissions.LUCKY_DRAW_VIEW, admin_perms)
        self.assertIn(Permissions.ROSTER_EDIT, admin_perms)
        self.assertIn(Permissions.VOTING_TRACK_PROGRESS, admin_perms)
        
        staff_perms = self.role_permissions_map['staff']
        self.assertIn(Permissions.ROSTER_VIEW, staff_perms)
        self.assertIn(Permissions.LUCKY_DRAW_VIEW, staff_perms)
        self.assertNotIn(Permissions.ROSTER_EDIT, staff_perms)

    def check_matrix(self, role, status, resource_template):
        # 1. Setup
        if role != 'guest':
            self.logout()
            self.login(role)
        else:
            self.logout()
            
        # 2. Derive Permissions
        perms = self.role_permissions_map[role]
        
        # 3. Derive Expectation
        expected_code = 200
        
        # --- LOGIC RULES ---
        
        # Rule: Guest Access (General)
        if role == 'guest':
            # Guests can only access specific public routes
            if '/pathway_library' in resource_template:
                expected_code = 200
            elif '/agenda' in resource_template:
                # GUEST -> AGENDA: Redirect to meeting-notice for unpublished
                if status == 'unpublished':
                    expected_code = 302
                else:
                    expected_code = 200
            elif '/voting' in resource_template:
                # GUEST -> VOTING:
                if status == 'running':
                    expected_code = 200
                else:
                    # Unpublished/Notstarted/Finished -> Redirect -> 302
                    expected_code = 302
            else:
                expected_code = 302 # Default deny
        
        else: # Authenticated User
            
            # Agenda / Booking Logic
            if '/agenda' in resource_template:
                # Unpublished requires VOTING_VIEW_RESULTS (Officers)
                if status == 'unpublished':
                    if Permissions.VOTING_VIEW_RESULTS not in perms:
                        expected_code = 302  # Redirect to meeting-notice
                    else:
                        expected_code = 200  # Officers can view
                else:
                    expected_code = 200

            if '/booking' in resource_template:
                if status == 'unpublished':
                    # Unpublished requires VOTING_VIEW_RESULTS (Officers)
                    if Permissions.VOTING_VIEW_RESULTS not in perms:
                        expected_code = 302

            # Voting Logic
            if '/voting' in resource_template:
                if status in ['unpublished', 'not started']:
                    if Permissions.VOTING_TRACK_PROGRESS not in perms:
                         expected_code = 302
                elif status == 'finished':
                    # Finished meetings: Only users with VOTING_VIEW_RESULTS can see results
                    if Permissions.VOTING_VIEW_RESULTS not in perms:
                        expected_code = 302

            # Resource Logic
            if '/lucky_draw' in resource_template:
                if Permissions.LUCKY_DRAW_VIEW not in perms:
                    expected_code = 302
            
            if '/roster' in resource_template:
                if Permissions.ROSTER_VIEW not in perms:
                    expected_code = 302
            
            if '/contacts' in resource_template:
                 if Permissions.CONTACT_BOOK_VIEW not in perms:
                     expected_code = 302

            if '/speech_logs' in resource_template:
                 # Members can navigate to speech logs (View Own?)
                 # For now, check 200 is accessible.
                 pass

            if '/settings' in resource_template or '/users' in resource_template:
                 if Permissions.SETTINGS_VIEW_ALL not in perms:
                     expected_code = 302
                 elif '/users' in resource_template:
                     expected_code = 302 # Redirect to settings tab

        # 4. Execute
        url = resource_template
        if '{}' in url:
            meeting = self.meetings.get(status) # Can be None for some tests
            if meeting:
                url = url.format(meeting.Meeting_Number)
        
        # Skip if no meeting for context
        if '{}' in resource_template and not meeting:
            return

        resp = self.client.get(url)
        
        with self.subTest(role=role, status=status, url=url):
            self.assertEqual(resp.status_code, expected_code, 
                             f"Result match. Role={role}, status={status}. Expected {expected_code}, Got {resp.status_code}")

    def test_agenda_matrix(self):
        for role in self.ALL_ROLES:
            for status in self.ALL_STATUSES:
                self.check_matrix(role, status, '/agenda?meeting_number={}')

    def test_booking_matrix(self):
        for role in self.ALL_ROLES:
            for status in self.ALL_STATUSES:
                # Booking: Guest -> 302. Member+ -> 200 (unless unpublished).
                self.check_matrix(role, status, '/booking/{}')

    def test_voting_matrix(self):
        for role in self.ALL_ROLES:
            for status in self.ALL_STATUSES:
                self.check_matrix(role, status, '/voting/{}')

    def test_resource_matrix(self):
        for role in self.ALL_ROLES:
            for res in self.PUBLIC_RESOURCES:
                # Use 'running' status as dummy context if needed?
                self.check_matrix(role, 'running', res)

    def test_admin_matrix(self):
        for role in self.ALL_ROLES:
            for resource in self.ADMIN_RESOURCES:
                self.check_matrix(role, 'running', resource)

if __name__ == '__main__':
    unittest.main()
