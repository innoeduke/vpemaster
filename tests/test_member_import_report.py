import sys
import os
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Contact, UserClub, Message, Club, AuthRole
from app.services.member_import_service import process_member_file
from config import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ENGINE_OPTIONS = {}


class MemberImportReportTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Role needed for new user creation
        self.role_member = AuthRole(name="Member", level=1)
        db.session.add(self.role_member)

        # The "system" sender (User id 1) used when no current_user is provided
        sysadmin = User(username="sysadmin", email="sysadmin@example.com", status='active')
        sysadmin.set_password('password')
        db.session.add(sysadmin)

        self.club = Club(club_name="Test Club", club_no="111111")
        db.session.add(self.club)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def _csv_bytes(self, body):
        return ("Fullname,Username,Member ID,Email,Mentor Name\n" + body).encode("utf-8")

    def test_report_has_three_buckets(self):
        report = process_member_file(self._csv_bytes(""), 'csv', self.club.id)
        self.assertIn('added', report)
        self.assertIn('invited', report)
        self.assertIn('failed', report)
        self.assertEqual(report['added'], [])
        self.assertEqual(report['invited'], [])
        self.assertEqual(report['failed'], [])

    def test_new_user_lands_in_added(self):
        body = "Jane Doe,janed,12345,jane@example.com,\n"
        with self.app.test_request_context():
            report = process_member_file(self._csv_bytes(body), 'csv', self.club.id)
        self.assertEqual(len(report['added']), 1)
        self.assertEqual(report['added'][0]['username'], 'janed')
        self.assertEqual(report['added'][0]['fullname'], 'Jane Doe')
        self.assertEqual(report['added'][0]['email'], 'jane@example.com')
        self.assertEqual(report['invited'], [])
        self.assertEqual(report['failed'], [])

    def test_existing_user_in_other_club_lands_in_invited(self):
        # Pre-create a user that's not in our club
        existing = User(username="bob", email="bob@elsewhere.com", status='active')
        existing.set_password('password')
        db.session.add(existing)
        db.session.commit()

        body = "Bob Smith,bob,12345,bob@elsewhere.com,\n"
        with self.app.test_request_context():
            report = process_member_file(self._csv_bytes(body), 'csv', self.club.id)
        self.assertEqual(report['added'], [])
        self.assertEqual(len(report['invited']), 1)
        self.assertEqual(report['invited'][0]['username'], 'bob')
        self.assertEqual(report['failed'], [])

        # An invitation message was created
        msgs = Message.query.all()
        self.assertEqual(len(msgs), 1)
        self.assertIn('Invitation to join Test Club', msgs[0].subject)

    def test_existing_user_in_same_club_lands_in_failed(self):
        # Pre-create a user that IS already in this club
        existing = User(username="alice", email="alice@example.com", status='active')
        existing.set_password('password')
        db.session.add(existing)
        db.session.flush()
        contact = Contact(Name="Alice InClub", Email="alice@example.com", Type='Member')
        db.session.add(contact)
        db.session.flush()
        uc = UserClub(user_id=existing.id, club_id=self.club.id, contact_id=contact.id, is_home=True)
        db.session.add(uc)
        db.session.commit()

        body = "Alice InClub,alice,12345,alice@example.com,\n"
        with self.app.test_request_context():
            report = process_member_file(self._csv_bytes(body), 'csv', self.club.id)
        self.assertEqual(report['added'], [])
        self.assertEqual(report['invited'], [])
        self.assertEqual(len(report['failed']), 1)
        self.assertIn("alice", report['failed'][0])
        self.assertIn("Already a member", report['failed'][0])

    def test_missing_required_fields_lands_in_failed(self):
        body = ",noname,12345,no@one.com,Mentor\nNoUserHere,,12346,nu@one.com,Mentor\n"
        report = process_member_file(self._csv_bytes(body), 'csv', self.club.id)
        self.assertEqual(report['added'], [])
        self.assertEqual(report['invited'], [])
        self.assertEqual(len(report['failed']), 2)
        for f in report['failed']:
            self.assertIn("Fullname and Username are mandatory", f)

    def test_mixed_report(self):
        # 1) new user, 2) existing user in another club, 3) invalid row
        existing = User(username="bob", email="bob@elsewhere.com", status='active')
        existing.set_password('password')
        db.session.add(existing)
        db.session.commit()

        body = (
            "Carol New,caroln,1,carol@example.com,\n"
            "Bob Smith,bob,2,bob@elsewhere.com,\n"
            ",badrow,3,bad@one.com,\n"
        )
        with self.app.test_request_context():
            report = process_member_file(self._csv_bytes(body), 'csv', self.club.id)
        self.assertEqual(len(report['added']), 1)
        self.assertEqual(report['added'][0]['username'], 'caroln')
        self.assertEqual(len(report['invited']), 1)
        self.assertEqual(report['invited'][0]['username'], 'bob')
        self.assertEqual(len(report['failed']), 1)
        self.assertIn("Fullname and Username are mandatory", report['failed'][0])

    def test_empty_rows_are_skipped(self):
        body = "\n\n   \n,,\n"
        report = process_member_file(self._csv_bytes(body), 'csv', self.club.id)
        self.assertEqual(report['added'], [])
        self.assertEqual(report['invited'], [])
        self.assertEqual(report['failed'], [])

    def test_invalid_club_returns_failed_report(self):
        report = process_member_file(self._csv_bytes(""), 'csv', 99999)
        self.assertEqual(report['added'], [])
        self.assertEqual(report['invited'], [])
        self.assertTrue(any("Invalid club ID" in f for f in report['failed']))

    def test_unsupported_extension_returns_failed_report(self):
        report = process_member_file(b"", 'txt', self.club.id)
        self.assertEqual(report['added'], [])
        self.assertEqual(report['invited'], [])
        self.assertEqual(len(report['failed']), 1)
        self.assertIn("Unsupported file extension", report['failed'][0])


if __name__ == '__main__':
    unittest.main()
