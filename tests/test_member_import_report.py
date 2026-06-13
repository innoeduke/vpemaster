import sys
import os
import unittest
import unittest.mock as mock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Contact, UserClub, Message, Club, AuthRole, ContactClub
from app.services.member_import_service import process_member_file, generate_username
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
        return ("Fullname*,Username,Member Number,Email*,Phone,Mentor Name\n" + body).encode("utf-8")

    def test_report_has_three_buckets(self):
        report = process_member_file(self._csv_bytes(""), 'csv', self.club.id)
        self.assertIn('added', report)
        self.assertIn('invited', report)
        self.assertIn('failed', report)
        self.assertEqual(report['added'], [])
        self.assertEqual(report['invited'], [])
        self.assertEqual(report['failed'], [])

    def test_new_user_lands_in_added(self):
        body = "Jane Doe,janed,PN-12345,jane@example.com,,\n"
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

        body = "Bob Smith,bob,PN-12345,bob@elsewhere.com,,\n"
        with self.app.test_request_context():
            report = process_member_file(self._csv_bytes(body), 'csv', self.club.id)
        self.assertEqual(report['added'], [])
        self.assertEqual(len(report['invited']), 1)
        self.assertEqual(report['invited'][0]['username'], 'bob')
        self.assertEqual(report['failed'], [])

        # Check that UserClub linkage was NOT created (user is not added directly)
        uc = UserClub.query.filter_by(user_id=existing.id, club_id=self.club.id).first()
        self.assertIsNone(uc)

        # Check that Contact card was NOT created during import
        contact = Contact.query.filter_by(Email='bob@elsewhere.com').first()
        self.assertIsNone(contact)

        # Check that an invitation Message was sent to the user's inbox
        msg = Message.query.filter_by(recipient_id=existing.id).first()
        self.assertIsNotNone(msg)
        self.assertIn("Invitation to join", msg.subject)
        self.assertIn(f"[CLUB_ID:{self.club.id}]", msg.body)

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

        body = "Alice InClub,alice,PN-12345,alice@example.com,,\n"
        with self.app.test_request_context():
            report = process_member_file(self._csv_bytes(body), 'csv', self.club.id)
        self.assertEqual(report['added'], [])
        self.assertEqual(report['invited'], [])
        self.assertEqual(len(report['failed']), 1)
        self.assertIn("already a member of this club", report['failed'][0])

    def test_missing_fullname_lands_in_failed(self):
        body = ",noname,PN-12345,no@one.com,,\n"
        report = process_member_file(self._csv_bytes(body), 'csv', self.club.id)
        self.assertEqual(report['added'], [])
        self.assertEqual(report['invited'], [])
        self.assertEqual(len(report['failed']), 1)
        self.assertIn("Fullname is required", report['failed'][0])

    def test_mixed_report(self):
        # 1) new user (added), 2) existing user in another club (invited), 3) invalid row (failed)
        existing = User(username="bob", email="bob@elsewhere.com", status='active')
        existing.set_password('password')
        db.session.add(existing)
        db.session.commit()

        body = (
            "Carol New,caroln,PN-1,carol@example.com,,\n"
            "Bob Smith,bob,PN-2,bob@elsewhere.com,,\n"
            ",badrow,PN-3,bad@one.com,,\n"
        )
        with self.app.test_request_context():
            report = process_member_file(self._csv_bytes(body), 'csv', self.club.id)
        self.assertEqual(len(report['added']), 1)
        self.assertEqual(report['added'][0]['username'], 'caroln')
        self.assertEqual(len(report['invited']), 1)
        self.assertEqual(report['invited'][0]['username'], 'bob')
        self.assertEqual(len(report['failed']), 1)
        self.assertTrue(any("Fullname is required" in f for f in report['failed']))

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

    def test_invalid_column_headers_drops_task(self):
        # Header is missing 'Mentor Name' (only 5 columns)
        bad_headers_csv = "Fullname*,Username,Member Number,Email*,Phone\nJane Doe,janed,PN-12345,jane@example.com,+\n".encode("utf-8")
        report = process_member_file(bad_headers_csv, 'csv', self.club.id)
        self.assertEqual(report['added'], [])
        self.assertEqual(report['invited'], [])
        self.assertEqual(len(report['failed']), 1)
        self.assertIn("Invalid column headers", report['failed'][0])

        # Header has misspelled name
        bad_headers_csv2 = "Fullname*,User_Name_Typo,Member Number,Email*,Phone,Mentor Name\nJane Doe,janed,PN-12345,jane@example.com,,Mentor\n".encode("utf-8")
        report2 = process_member_file(bad_headers_csv2, 'csv', self.club.id)
        self.assertEqual(len(report2['failed']), 1)
        self.assertIn("Invalid column headers", report2['failed'][0])

    def test_optional_username_auto_generated(self):
        # 1. No username provided -> auto-generates 8 letters-only string based on name
        body = "Jane Doe,,PN-12345,jane@example.com,,\n"
        with self.app.test_request_context():
            report = process_member_file(self._csv_bytes(body), 'csv', self.club.id)
        self.assertEqual(len(report['added']), 1)
        username = report['added'][0]['username']
        self.assertEqual(len(username), 8)
        self.assertTrue(username.isalpha())
        self.assertEqual(username[:4], "jane")

        # 2. Collision resolution (starts with 'janedoe' + random letter, if collides replace trailing with digits)
        existing_username = "janedoe" + "x"
        user_conflict = User(username=existing_username, email="conflict@example.com", status='active')
        user_conflict.set_password('password')
        db.session.add(user_conflict)
        db.session.commit()

        # Let's mock random choices to return 'x'
        with self.app.test_request_context():
            with mock.patch('random.choices', return_value=['x']):
                gen = generate_username("Jane Doe")
                # Since 'janedoe' + 'x' exists globally, it should sequentially choose prefix + digits
                # prefix is 'janedoe' (7 letters). Replacing 1 letter at end yields: prefix + '0' -> 'janedoe0'
                self.assertEqual(gen, 'janedoe0')

    def test_member_number_format_validation(self):
        # 1. Invalid Member Number prefix
        body1 = "Jane Doe,janed,12345,jane@example.com,,\n"
        report1 = process_member_file(self._csv_bytes(body1), 'csv', self.club.id)
        self.assertEqual(len(report1['failed']), 1)
        self.assertIn("Invalid Member Number format", report1['failed'][0])

        # 2. Valid format
        body2 = "Jane Doe,janed,PN-12345,jane@example.com,,\n"
        with self.app.test_request_context():
            report2 = process_member_file(self._csv_bytes(body2), 'csv', self.club.id)
        self.assertEqual(len(report2['added']), 1)

    def test_contact_club_scope_matching_and_linkage(self):
        # 1. Pre-create contact in another club
        other_club = Club(club_name="Other Club", club_no="222222")
        db.session.add(other_club)
        db.session.flush()

        contact_other = Contact(Name="Target User", Email="target@example.com", Type='Member')
        db.session.add(contact_other)
        db.session.flush()

        cc_other = ContactClub(contact_id=contact_other.id, club_id=other_club.id)
        db.session.add(cc_other)
        db.session.commit()

        # Import into our club: target@example.com is NOT a duplicate since contact is in other_club!
        body = "Target User,targetu,,target@example.com,,\n"
        with self.app.test_request_context():
            report = process_member_file(self._csv_bytes(body), 'csv', self.club.id)
        self.assertEqual(len(report['added']), 1)
        self.assertEqual(report['failed'], [])

        # 2. Pre-create contact in our TARGET club (unlinked to any user)
        contact_target = Contact(Name="Target User 2", Email="target2@example.com", Type='Member')
        db.session.add(contact_target)
        db.session.flush()
        cc_target = ContactClub(contact_id=contact_target.id, club_id=self.club.id)
        db.session.add(cc_target)
        db.session.commit()

        # Import target2@example.com. It should link to existing contact_target instead of creating a new one!
        body2 = "Target User 2,targetu2,,target2@example.com,,\n"
        with self.app.test_request_context():
            report2 = process_member_file(self._csv_bytes(body2), 'csv', self.club.id)
        self.assertEqual(len(report2['added']), 1)
        self.assertEqual(report2['failed'], [])

        # Verify UserClub has target2 user linked to contact_target.id
        user2 = User.query.filter_by(username='targetu2').first()
        self.assertIsNotNone(user2)
        uc = UserClub.query.filter_by(user_id=user2.id, club_id=self.club.id).first()
        self.assertIsNotNone(uc)
        self.assertEqual(uc.contact_id, contact_target.id)

    def test_file_level_duplication_validation(self):
        body = (
            "Jane Doe,janed,PN-12345,jane@example.com,,\n"
            "Alice Smith,janed,PN-12346,alice@example.com,,\n"  # duplicate username
        )
        with self.app.test_request_context():
            report = process_member_file(self._csv_bytes(body), 'csv', self.club.id)
        self.assertEqual(len(report['added']), 1)
        self.assertEqual(len(report['failed']), 1)
        self.assertIn("duplicated in the uploaded file", report['failed'][0])

    def test_missing_email_lands_in_failed(self):
        body = "Jane Doe,janed,PN-12345,,,\n"
        with self.app.test_request_context():
            report = process_member_file(self._csv_bytes(body), 'csv', self.club.id)
        self.assertEqual(report['added'], [])
        self.assertEqual(report['invited'], [])
        self.assertEqual(len(report['failed']), 1)
        self.assertIn("Email is required", report['failed'][0])


if __name__ == '__main__':
    unittest.main()
