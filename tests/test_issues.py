import sys
import os
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import (
    Issue, IssueComment, Message, User, Club, Contact, UserClub,
    AuthRole, Permission,
)
from app.auth.permissions import Permissions
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ENGINE_OPTIONS = {}


class IssuesRouteTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Roles & permissions
        self.role_admin = AuthRole(name="ClubAdmin", level=4)
        self.role_member = AuthRole(name="Member", level=1)
        self.perm_issue_manage = Permission(name=Permissions.ISSUE_MANAGE, description="Manage Issues")
        self.role_admin.permissions.append(self.perm_issue_manage)
        db.session.add_all([self.role_admin, self.role_member, self.perm_issue_manage])

        # Two clubs
        self.club_a = Club(club_name="Club A", club_no="111111")
        self.club_b = Club(club_name="Club B", club_no="222222")
        db.session.add_all([self.club_a, self.club_b])
        db.session.commit()

        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def create_user(self, username, role_name, club):
        c = Contact(Name=username, Email=f"{username}@example.com", Type='Member')
        db.session.add(c)
        db.session.flush()

        u = User(username=username, email=f"{username}@example.com", status='active')
        u.set_password('password')
        db.session.add(u)
        db.session.flush()

        role = AuthRole.query.filter_by(name=role_name).first()
        uc = UserClub(
            user_id=u.id, club_id=club.id, contact_id=c.id, is_home=True,
            auth_role_id=role.id if role else None,
        )
        db.session.add(uc)
        db.session.commit()
        db.session.refresh(u)
        return u, c

    def login(self, username, club):
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data=dict(
            username=username,
            password='password',
            club_names=str(club.id)
        ), follow_redirects=True)
        with self.client.session_transaction() as sess:
            sess['club_id'] = club.id
            sess['current_club_id'] = club.id

    def _make_issue(self, club, submitter, **overrides):
        defaults = dict(
            club_id=club.id,
            type=Issue.TYPE_BUG,
            status=Issue.STATUS_OPEN,
            priority=Issue.PRIORITY_MEDIUM,
            title="Sample issue",
            description="Sample description",
            submitter_id=submitter.id,
        )
        defaults.update(overrides)
        issue = Issue(**defaults)
        db.session.add(issue)
        db.session.commit()
        return issue

    def test_unauthenticated_redirected_to_login(self):
        res = self.client.get('/issues/')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res.headers.get('Location', ''))

    def test_member_can_view_list_and_create_issue(self):
        member, _ = self.create_user("alice", "Member", self.club_a)
        self.login("alice", self.club_a)

        res = self.client.get('/issues/')
        self.assertEqual(res.status_code, 200)

        res = self.client.post('/issues/new', json=dict(
            title="Login form broken",
            description="Submit button does nothing",
            type=Issue.TYPE_BUG,
            priority=Issue.PRIORITY_HIGH,
        ))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])
        self.assertIn('id', res.get_json())

        issue = Issue.query.filter_by(title="Login form broken").first()
        self.assertIsNotNone(issue)
        self.assertEqual(issue.submitter_id, member.id)
        self.assertEqual(issue.status, Issue.STATUS_OPEN)
        self.assertEqual(issue.priority, Issue.PRIORITY_HIGH)

    def test_create_issue_via_get_redirects(self):
        """GET on /issues/new should not render a form (modal lives client-side)."""
        member, _ = self.create_user("alice", "Member", self.club_a)
        self.login("alice", self.club_a)
        res = self.client.get('/issues/new')
        self.assertIn(res.status_code, (405, 404))

    def test_create_issue_validates_required_fields(self):
        member, _ = self.create_user("alice", "Member", self.club_a)
        self.login("alice", self.club_a)

        res = self.client.post('/issues/new', json=dict(
            title="",
            description="",
            type=Issue.TYPE_BUG,
            priority=Issue.PRIORITY_MEDIUM,
        ))
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json()['success'])
        self.assertEqual(Issue.query.count(), 0)

    def test_admin_can_update_issue_and_sets_closed_at(self):
        admin, _ = self.create_user("admin", "ClubAdmin", self.club_a)
        issue = self._make_issue(self.club_a, admin)

        self.login("admin", self.club_a)
        res = self.client.post(f'/issues/{issue.id}/update', data=dict(
            status=Issue.STATUS_CLOSED,
            priority=Issue.PRIORITY_LOW,
            title=issue.title,
            description=issue.description,
        ), follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        db.session.refresh(issue)
        self.assertEqual(issue.status, Issue.STATUS_CLOSED)
        self.assertIsNotNone(issue.closed_at)
        self.assertEqual(issue.priority, Issue.PRIORITY_LOW)

    def test_admin_assigning_user_sends_system_message(self):
        admin, _ = self.create_user("admin", "ClubAdmin", self.club_a)
        target, _ = self.create_user("bob", "ClubAdmin", self.club_a)
        issue = self._make_issue(self.club_a, admin)

        before_count = Message.query.filter_by(recipient_id=target.id).count()

        self.login("admin", self.club_a)
        res = self.client.post(f'/issues/{issue.id}/update', data=dict(
            status=issue.status,
            priority=issue.priority,
            title=issue.title,
            description=issue.description,
            assignee_id=str(target.id),
        ), follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        db.session.refresh(issue)
        self.assertEqual(issue.assignee_id, target.id)
        self.assertEqual(
            Message.query.filter_by(recipient_id=target.id).count(),
            before_count + 1,
        )
        msg = (
            Message.query.filter_by(recipient_id=target.id)
            .order_by(Message.id.desc()).first()
        )
        self.assertIn(f'#{issue.id}', msg.subject)

    def test_comment_allowed_on_open_but_blocked_on_closed(self):
        admin, _ = self.create_user("admin", "ClubAdmin", self.club_a)
        issue = self._make_issue(self.club_a, admin)

        self.login("admin", self.club_a)

        res = self.client.post(f'/issues/{issue.id}/comment', data=dict(
            body="Initial comment",
        ), follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            IssueComment.query.filter_by(issue_id=issue.id).count(), 1,
        )

        res = self.client.post(f'/issues/{issue.id}/update', data=dict(
            status=Issue.STATUS_CLOSED,
            priority=issue.priority,
            title=issue.title,
            description=issue.description,
        ), follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        res = self.client.post(f'/issues/{issue.id}/comment', data=dict(
            body="Late comment",
        ), follow_redirects=False)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(
            IssueComment.query.filter_by(issue_id=issue.id).count(), 1,
        )

    def test_cross_club_issue_returns_404(self):
        admin_a, _ = self.create_user("admin_a", "ClubAdmin", self.club_a)
        admin_b, _ = self.create_user("admin_b", "ClubAdmin", self.club_b)
        issue_b = self._make_issue(self.club_b, admin_b)

        self.login("admin_a", self.club_a)
        res = self.client.get(f'/issues/{issue_b.id}')
        self.assertEqual(res.status_code, 404)

    def test_empty_comment_rejected(self):
        admin, _ = self.create_user("admin", "ClubAdmin", self.club_a)
        issue = self._make_issue(self.club_a, admin)
        self.login("admin", self.club_a)

        res = self.client.post(f'/issues/{issue.id}/comment', data=dict(
            body="   ",
        ), follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            IssueComment.query.filter_by(issue_id=issue.id).count(), 0,
        )

    def test_create_issue_validates_required_fields_via_form(self):
        """Form-encoded POST should still validate and return 400."""
        member, _ = self.create_user("alice", "Member", self.club_a)
        self.login("alice", self.club_a)

        res = self.client.post('/issues/new', data=dict(
            title="",
            description="",
            type=Issue.TYPE_BUG,
            priority=Issue.PRIORITY_MEDIUM,
        ))
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json()['success'])
        self.assertEqual(Issue.query.count(), 0)

    def test_member_cannot_update_issue(self):
        member, _ = self.create_user("alice", "Member", self.club_a)
        admin, _ = self.create_user("admin", "ClubAdmin", self.club_a)
        issue = self._make_issue(self.club_a, admin)

        self.login("alice", self.club_a)
        res = self.client.post(f'/issues/{issue.id}/update', data=dict(
            status=Issue.STATUS_CLOSED,
            priority=Issue.PRIORITY_LOW,
            title=issue.title,
            description=issue.description,
        ), follow_redirects=True)
        self.assertEqual(res.status_code, 403)

    def test_member_can_comment_on_other_members_issue(self):
        admin, _ = self.create_user("admin", "ClubAdmin", self.club_a)
        alice, _ = self.create_user("alice", "Member", self.club_a)
        issue = self._make_issue(self.club_a, admin)

        self.login("alice", self.club_a)
        res = self.client.post(f'/issues/{issue.id}/comment', data=dict(
            body="I can reproduce this.",
        ), follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            IssueComment.query.filter_by(issue_id=issue.id, author_id=alice.id).count(),
            1,
        )

    def test_assignable_users_filtered_to_issue_manage_holders(self):
        """Only users with ISSUE_MANAGE in the club appear in the assignable list."""
        admin, _ = self.create_user("admin", "ClubAdmin", self.club_a)
        member, _ = self.create_user("member", "Member", self.club_a)
        # Manager in club B - should NOT appear in club A's list
        admin_b, _ = self.create_user("admin_b", "ClubAdmin", self.club_b)

        # Anonymous access to the API is denied
        res = self.client.get('/issues/api/assignable-users')
        self.assertEqual(res.status_code, 302)

        self.login("admin", self.club_a)
        res = self.client.get('/issues/api/assignable-users')
        self.assertEqual(res.status_code, 200)
        ids = {u['id'] for u in res.get_json()}
        self.assertIn(admin.id, ids)
        self.assertNotIn(member.id, ids)
        self.assertNotIn(admin_b.id, ids)

    def test_cannot_assign_to_user_without_issue_manage(self):
        """Server rejects assigning to a non-permitted user even if the UI allowed it."""
        admin, _ = self.create_user("admin", "ClubAdmin", self.club_a)
        member, _ = self.create_user("member", "Member", self.club_a)
        issue = self._make_issue(self.club_a, admin)

        self.login("admin", self.club_a)
        res = self.client.post(f'/issues/{issue.id}/update', data=dict(
            status=issue.status,
            priority=issue.priority,
            title=issue.title,
            description=issue.description,
            assignee_id=str(member.id),
        ), follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        db.session.refresh(issue)
        self.assertIsNone(issue.assignee_id)

    def test_super_club_can_view_all_issues(self):
        """Sysadmin in the super club context can view all issues across all clubs."""
        sysadmin, _ = self.create_user("sysadmin", "ClubAdmin", self.club_a)

        # Create issues in club_a and club_b
        issue_a = self._make_issue(self.club_a, sysadmin, title="Club A Issue")

        user_b, _ = self.create_user("user_b", "Member", self.club_b)
        issue_b = self._make_issue(self.club_b, user_b, title="Club B Issue")

        # 1. Log in normal member in club_a -> can only see issue_a
        member, _ = self.create_user("member", "Member", self.club_a)
        self.login("member", self.club_a)
        res = self.client.get('/issues/')
        self.assertEqual(res.status_code, 200)
        self.assertIn("Club A Issue", res.get_data(as_text=True))
        self.assertNotIn("Club B Issue", res.get_data(as_text=True))

        # 2. Log in sysadmin in the super club context (club_a is ID 1) -> can see both
        self.login("sysadmin", self.club_a)
        res = self.client.get('/issues/')
        self.assertEqual(res.status_code, 200)
        self.assertIn("Club A Issue", res.get_data(as_text=True))
        self.assertIn("Club B Issue", res.get_data(as_text=True))

    def test_default_filter_includes_closed_issues(self):
        admin, _ = self.create_user("admin", "ClubAdmin", self.club_a)
        self.login("admin", self.club_a)
        
        # Create an open and a closed issue
        self._make_issue(self.club_a, admin, title="Open Issue", status=Issue.STATUS_OPEN)
        self._make_issue(self.club_a, admin, title="Closed Issue", status=Issue.STATUS_CLOSED)
        
        # Default view (no status param): should show Open and Closed
        res = self.client.get('/issues/')
        self.assertEqual(res.status_code, 200)
        self.assertIn("Open Issue", res.get_data(as_text=True))
        self.assertIn("Closed Issue", res.get_data(as_text=True))
        
        # Filter status=closed: should show Closed, hide Open
        res = self.client.get('/issues/?status=closed')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("Open Issue", res.get_data(as_text=True))
        self.assertIn("Closed Issue", res.get_data(as_text=True))
        
        # Filter status="" (All): should show both
        res = self.client.get('/issues/?status=')
        self.assertEqual(res.status_code, 200)
        self.assertIn("Open Issue", res.get_data(as_text=True))
        self.assertIn("Closed Issue", res.get_data(as_text=True))

    def test_assignee_change_sets_in_progress_and_close_sets_closed(self):
        admin, _ = self.create_user("admin", "ClubAdmin", self.club_a)
        target, _ = self.create_user("bob", "ClubAdmin", self.club_a)
        issue = self._make_issue(self.club_a, admin, status=Issue.STATUS_OPEN)
        
        self.login("admin", self.club_a)
        
        # Assigning the issue -> should set status to in_progress
        res = self.client.post(f'/issues/{issue.id}/update', data=dict(
            status=issue.status,
            priority=issue.priority,
            title=issue.title,
            description=issue.description,
            assignee_id=str(target.id),
        ), follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        
        db.session.refresh(issue)
        self.assertEqual(issue.assignee_id, target.id)
        self.assertEqual(issue.status, Issue.STATUS_IN_PROGRESS)
        
        # Closing the issue via close button parameter -> should set status to closed
        res = self.client.post(f'/issues/{issue.id}/update', data=dict(
            status=issue.status,
            priority=issue.priority,
            title=issue.title,
            description=issue.description,
            assignee_id=str(target.id),
            close_issue="true",
        ), follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        
        db.session.refresh(issue)
        self.assertEqual(issue.status, Issue.STATUS_CLOSED)

    def test_contributors_saved_via_update(self):
        admin, _ = self.create_user("admin", "ClubAdmin", self.club_a)
        issue = self._make_issue(self.club_a, admin)
        
        self.login("admin", self.club_a)
        res = self.client.post(f'/issues/{issue.id}/update', data=dict(
            status=issue.status,
            priority=issue.priority,
            title=issue.title,
            description=issue.description,
            contributors="Alice, Charlie",
        ), follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        
        db.session.refresh(issue)
        self.assertEqual(issue.contributors, "Alice, Charlie")


if __name__ == '__main__':
    unittest.main()
