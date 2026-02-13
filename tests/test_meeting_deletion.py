import unittest
import sys
import os
from datetime import datetime, date, time

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Meeting, SessionLog, SessionType, Waitlist, Vote, Roster, RosterRole, Contact, Media, Planner, User
from app.models.roster import MeetingRole
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class MeetingDeletionTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.populate_base_data()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def populate_base_data(self):
        # Create minimal required data types
        self.role = MeetingRole(name="Speaker", type="speech", needs_approval=False, has_single_owner=False)
        db.session.add(self.role)
        db.session.commit()

        self.st = SessionType(Title="Prepared Speech", role_id=self.role.id)
        db.session.add(self.st)
        
        self.contact = Contact(Name="Test User")
        db.session.add(self.contact)
        
        # Create Club (required for Meeting)
        from app.models import Club
        self.club = Club(
            club_no='000000',
            club_name='Test Club',
            district='Test District'
        )
        db.session.add(self.club)
        
        from werkzeug.security import generate_password_hash
        self.user = User(
            username="testuser", 
            email="test@test.com",
            password_hash=generate_password_hash("testpassword")
        )
        db.session.add(self.user)
        db.session.commit()
        
        # Link contact to user
        from app.models import UserClub
        uc = UserClub(user=self.user, contact=self.contact, club=self.club)
        db.session.add(uc)
        db.session.commit()

    def create_meeting(self, meeting_number=100):
        meeting = Meeting(
            Meeting_Number=meeting_number,
            Meeting_Date=date.today(),
            Start_Time=time(19, 0),
            status='finished',
            club_id=self.club.id
        )
        db.session.add(meeting)
        db.session.commit()
        return meeting

    def test_delete_meeting_success(self):
        meeting_num = 101
        meeting = self.create_meeting(meeting_num)
        
        # Add associated data
        log = SessionLog(
            Meeting_Number=meeting_num, 
            Type_ID=self.st.id, 
            owners=[self.contact]
        )
        db.session.add(log)
        db.session.commit()
        
        # Add Waitlist
        wl = Waitlist(session_log_id=log.id, contact_id=self.contact.id)
        db.session.add(wl)
        
        # Add Vote
        vote = Vote(meeting_id=meeting.id, voter_identifier="tester")
        db.session.add(vote)
        
        # Add Roster
        roster = Roster(meeting_id=meeting.id, contact_id=self.contact.id)
        db.session.add(roster)
        db.session.commit()
        
        # Add RosterRole
        rr = RosterRole(roster_id=roster.id, role_id=self.role.id)
        db.session.add(rr)
        
        # Add Planner entry
        planner = Planner(
            meeting_id=meeting.id,
            user_id=self.user.id,
            club_id=self.club.id,
            meeting_role_id=self.role.id,
            status='draft'
        )
        db.session.add(planner)
        db.session.commit()

        # Verify data exists
        self.assertIsNotNone(Meeting.query.filter_by(Meeting_Number=meeting_num).first())
        self.assertEqual(SessionLog.query.count(), 1)
        self.assertEqual(Waitlist.query.count(), 1)
        self.assertEqual(Vote.query.count(), 1)
        self.assertEqual(Roster.query.count(), 1)
        self.assertEqual(RosterRole.query.count(), 1)
        self.assertEqual(Planner.query.count(), 1)

        # Execute Deletion
        success, msg = meeting.delete_full()
        
        # Verify result
        self.assertTrue(success)
        self.assertIsNone(Meeting.query.filter_by(Meeting_Number=meeting_num).first())
        self.assertEqual(SessionLog.query.count(), 0)
        self.assertEqual(Waitlist.query.count(), 0)
        self.assertEqual(Vote.query.count(), 0)
        self.assertEqual(Roster.query.count(), 0)
        self.assertEqual(RosterRole.query.count(), 0)
        self.assertEqual(Planner.query.count(), 0)

    def test_delete_meeting_with_media(self):
        meeting_num = 102
        meeting = self.create_meeting(meeting_num)
        
        media = Media(url="http://test.com")
        db.session.add(media)
        db.session.commit()
        
        meeting.media_id = media.id
        db.session.add(meeting)
        db.session.commit() # Important to commit the link

        # Verify link
        self.assertIsNotNone(meeting.media)

        # Execute Deletion
        success, msg = meeting.delete_full()
        
        self.assertTrue(success)
        self.assertIsNone(Meeting.query.filter_by(Meeting_Number=meeting_num).first())
        self.assertIsNone(db.session.get(Media, media.id))


    def test_delete_session_log_media(self):
        meeting_num = 103
        meeting = self.create_meeting(meeting_num)
        
        # Create SessionLog with Media
        log = SessionLog(
            Meeting_Number=meeting_num, 
            Type_ID=self.st.id, 
            owners=[self.contact]
        )
        db.session.add(log)
        db.session.commit() # Commit to get log.id
        
        media = Media(url="http://test-log-media.com")
        log.media = media # Association
        db.session.add(media)
        db.session.add(log)
        db.session.commit()
        
        media_id = media.id
        
        # Verify existence
        self.assertIsNotNone(db.session.get(Media, media_id))
        
        # Execute Deletion via Meeting.delete_full() which calls SessionLog.delete_for_meeting()
        meeting.delete_full()
        
        # Verify Media is gone
        self.assertIsNone(db.session.get(Media, media_id))

if __name__ == '__main__':
    unittest.main()
