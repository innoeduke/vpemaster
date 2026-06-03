import unittest
import sys
import os
from datetime import date

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Contact, AuthRole, Meeting, Permission, UserClub, Vote
from app.auth.permissions import Permissions
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class VotingRealtimeTestCase(unittest.TestCase):
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
        # Create Roles
        self.roles = {}
        for name, level in [('SysAdmin', 10), ('ClubAdmin', 5), ('Staff', 2), ('User', 1), ('Guest', 0)]:
            role = AuthRole(name=name, description=f"{name} Role", level=level if level is not None else 0)
            db.session.add(role)
            self.roles[name] = role
        
        # Create Club
        from app.models import Club
        self.club = Club(
            club_no='000000',
            club_name='Test Club',
            district='Test District'
        )
        db.session.add(self.club)
        db.session.flush()

        # Create Users
        self.users = {}
        for role_name in ['SysAdmin', 'ClubAdmin', 'Staff', 'User']:
            contact = Contact(Name=f"{role_name} User", Type="Member")
            db.session.add(contact)
            db.session.flush()
            
            user = User(
                username=role_name.lower(),
                email=f"{role_name.lower()}@test.com"
            )
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            
            uc = UserClub(user_id=user.id, club_id=self.club.id, club_role_level=self.roles[role_name].level, contact_id=contact.id)
            db.session.add(uc)
            self.users[role_name.lower()] = user

        # Define Permissions
        all_perms_map = {
            'SysAdmin': [
                Permissions.VOTING_TRACK_PROGRESS, Permissions.VOTING_VIEW_RESULTS
            ],
            'ClubAdmin': [
                Permissions.VOTING_TRACK_PROGRESS, Permissions.VOTING_VIEW_RESULTS
            ],
            'Staff': [
                Permissions.VOTING_VIEW_RESULTS
            ],
            'User': [
                Permissions.MEETING_VIEW_PUBLISHED
            ]
        }
        
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

        # Create Meeting
        self.meeting = Meeting(
            Meeting_Number=100, 
            Meeting_Date=date.today(), 
            status='running',
            club_id=self.club.id
        )
        db.session.add(self.meeting)
        db.session.flush()

        # Create Contact A and Contact B to vote for
        self.contact_a = Contact(Name="Contact A")
        self.contact_b = Contact(Name="Contact B")
        db.session.add_all([self.contact_a, self.contact_b])
        db.session.flush()

        # Populate votes:
        # Voter 1 votes for contact A
        db.session.add(Vote(meeting_id=self.meeting.id, voter_identifier="voter1", award_category="speaker", contact_id=self.contact_a.id))
        # Voter 2 votes for contact A
        db.session.add(Vote(meeting_id=self.meeting.id, voter_identifier="voter2", award_category="speaker", contact_id=self.contact_a.id))
        # Voter 2 votes for contact B for evaluator
        db.session.add(Vote(meeting_id=self.meeting.id, voter_identifier="voter2", award_category="evaluator", contact_id=self.contact_b.id))
        
        db.session.commit()

    def login(self, username):
        return self.client.post('/login', data=dict(
            username=f"{username}@test.com",
            password="password"
        ), follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_anonymous_access_denied(self):
        """Anonymous guest should be redirected or unauthorized (403 or 302)."""
        self.logout()
        resp = self.client.get(f'/voting/{self.meeting.id}/live_results')
        self.assertIn(resp.status_code, [302, 401, 403])

    def test_unauthorized_role_access_denied(self):
        """User without VOTING_TRACK_PROGRESS should get 403."""
        self.login('user')
        resp = self.client.get(f'/voting/{self.meeting.id}/live_results')
        self.assertEqual(resp.status_code, 403)

    def test_staff_role_access_denied(self):
        """Staff (only has VOTING_VIEW_RESULTS, not VOTING_TRACK_PROGRESS) should get 403."""
        self.login('staff')
        resp = self.client.get(f'/voting/{self.meeting.id}/live_results')
        self.assertEqual(resp.status_code, 403)

    def test_authorized_role_success(self):
        """ClubAdmin/SysAdmin with VOTING_TRACK_PROGRESS should succeed."""
        self.login('clubadmin')
        
        # We need to simulate active club in session
        with self.client.session_transaction() as sess:
            sess['current_club_id'] = self.club.id

        resp = self.client.get(f'/voting/{self.meeting.id}/live_results')
        self.assertEqual(resp.status_code, 200)
        
        data = resp.get_json()
        self.assertTrue(data['success'])
        # Unique voters = 2 ('voter1', 'voter2')
        self.assertEqual(data['total_voters'], 2)
        
        # Verify vote counts returned
        votes = data['votes']
        self.assertEqual(len(votes), 2)
        
        # Extract vote details for comparison
        vote_details = {(v['contact_id'], v['award_category']): v['count'] for v in votes}
        self.assertEqual(vote_details[(self.contact_a.id, 'speaker')], 2)
        self.assertEqual(vote_details[(self.contact_b.id, 'evaluator')], 1)

if __name__ == '__main__':
    unittest.main()
