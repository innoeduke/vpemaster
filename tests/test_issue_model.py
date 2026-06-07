import sys
import os
import unittest
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Issue, IssueComment, User, Club, Contact, UserClub, AuthRole, Permission
from app.auth.permissions import Permissions
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ENGINE_OPTIONS = {}


class IssueModelTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        self.club = Club(club_name="Test Club", club_no="123456")
        db.session.add(self.club)
        db.session.flush()

        c = Contact(Name="tester", Email="tester@example.com", Type='Member')
        db.session.add(c)
        db.session.flush()
        self.user = User(username="tester", email="tester@example.com", status='active')
        self.user.set_password('password')
        db.session.add(self.user)
        db.session.flush()

        uc = UserClub(user_id=self.user.id, club_id=self.club.id, contact_id=c.id, is_home=True)
        db.session.add(uc)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def _make_issue(self, **overrides):
        defaults = dict(
            club_id=self.club.id,
            type=Issue.TYPE_BUG,
            status=Issue.STATUS_OPEN,
            priority=Issue.PRIORITY_MEDIUM,
            title="Login broken",
            description="Cannot log in",
            submitter_id=self.user.id,
        )
        defaults.update(overrides)
        issue = Issue(**defaults)
        db.session.add(issue)
        db.session.commit()
        return issue

    def test_defaults_on_creation(self):
        issue = self._make_issue()
        self.assertEqual(issue.status, Issue.STATUS_OPEN)
        self.assertEqual(issue.priority, Issue.PRIORITY_MEDIUM)
        self.assertEqual(issue.type, Issue.TYPE_BUG)
        self.assertIsNotNone(issue.created_at)
        self.assertIsNotNone(issue.updated_at)
        self.assertIsNone(issue.closed_at)
        self.assertIsNone(issue.assignee_id)

    def test_submitter_and_assignee_relationships(self):
        other = User(username="dev", email="dev@example.com", status='active')
        other.set_password('password')
        db.session.add(other)
        db.session.commit()
        issue = self._make_issue(assignee_id=other.id)

        self.assertEqual(issue.submitter.id, self.user.id)
        self.assertEqual(issue.assignee.id, other.id)
        self.assertIn(issue, self.user.submitted_issues)
        self.assertIn(issue, other.assigned_issues)

    def test_is_terminal(self):
        self.assertFalse(self._make_issue(status=Issue.STATUS_OPEN).is_terminal())
        self.assertFalse(self._make_issue(status=Issue.STATUS_IN_PROGRESS).is_terminal())
        self.assertTrue(self._make_issue(status=Issue.STATUS_CLOSED).is_terminal())
        self.assertTrue(self._make_issue(status=Issue.STATUS_REJECTED).is_terminal())
        self.assertTrue(self._make_issue(status=Issue.STATUS_CANCELLED).is_terminal())

    def test_comments_ordered_by_creation(self):
        issue = self._make_issue()
        first = IssueComment(issue_id=issue.id, author_id=self.user.id, body="First")
        db.session.add(first)
        db.session.commit()
        second = IssueComment(issue_id=issue.id, author_id=self.user.id, body="Second")
        db.session.add(second)
        db.session.commit()

        bodies = [c.body for c in issue.comments]
        self.assertEqual(bodies, ["First", "Second"])
        self.assertIn(first, self.user.issue_comments)

    def test_timestamps_set_automatically(self):
        before = datetime.now(timezone.utc)
        issue = self._make_issue()
        after = datetime.now(timezone.utc)
        # SQLite strips tz info on round-trip; strip on our side to compare
        created = issue.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        self.assertGreaterEqual(created, before)
        self.assertLessEqual(created, after)


if __name__ == '__main__':
    unittest.main()
