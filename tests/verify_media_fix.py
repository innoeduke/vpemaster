import unittest
from app import create_app, db
from app.models import SessionLog, SessionType, Meeting, Media, MeetingRole, Club
from datetime import date

class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test-secret'
    WTF_CSRF_ENABLED = False

class VerifyMediaFix(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.seed_data()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def seed_data(self):
        # Create a test club
        self.club = Club(
            club_no='000000',
            club_name='Test Club',
            district='Test District',
            division='Test Division',
            area='Test Area'
        )
        db.session.add(self.club)
        db.session.commit()

        # Add role and session type
        role = MeetingRole(name='Speaker', type='standard', needs_approval=False, has_single_owner=True, club_id=self.club.id)
        db.session.add(role)
        db.session.commit()

        self.st = SessionType(Title='Prepared Speech', role_id=role.id, club_id=self.club.id)
        db.session.add(self.st)
        db.session.commit()

        # Add meeting and log
        self.meeting = Meeting(Meeting_Number=1, Meeting_Date=date.today(), club_id=self.club.id)
        db.session.add(self.meeting)
        db.session.commit()

        self.log = SessionLog(id=1, Meeting_Number=1, Type_ID=self.st.id, Session_Title="Original Title")
        db.session.add(self.log)
        db.session.commit()

    def test_media_url_persists_after_refresh_with_flush(self):
        """Verify that media_url persists after refresh if flushed first."""
        log = db.session.get(SessionLog, 1)
        
        # 1. Update Media URL
        test_url = "https://youtube.com/test"
        log.update_media(test_url)
        log.Session_Title = "Updated Title"
        
        # 2. Flush and Refresh (The Fix)
        db.session.flush()
        db.session.refresh(log)
        
        # 3. Verify changes are still there
        self.assertEqual(log.Session_Title, "Updated Title")
        self.assertIsNotNone(log.media)
        self.assertEqual(log.media.url, test_url)

    def test_media_url_lost_after_refresh_without_flush(self):
        """Verify that media_url IS LOST after refresh if NOT flushed (proving the bug)."""
        log = db.session.get(SessionLog, 1)
        
        # 1. Update Media URL
        test_url = "https://youtube.com/test-bug"
        log.update_media(test_url)
        log.Session_Title = "Bug Title"
        
        # 2. Refresh WITHOUT Flush (The Bug)
        db.session.refresh(log)
        
        # 3. Verify changes are lost (back to original or None)
        self.assertEqual(log.Session_Title, "Original Title")
        self.assertIsNone(log.media)

if __name__ == '__main__':
    unittest.main()
