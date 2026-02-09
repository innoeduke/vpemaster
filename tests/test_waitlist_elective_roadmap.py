import unittest
from datetime import date
from app import create_app, db
from app.models import LevelRole, SessionLog, Contact, Meeting, SessionType, MeetingRole, Club
from app.speech_logs_routes import _calculate_completion_summary

class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test-secret'
    WTF_CSRF_ENABLED = False

class TestWaitlistElectiveRoadmap(unittest.TestCase):
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
        self.club = Club(club_no='000000', club_name='Test Club')
        db.session.add(self.club)
        db.session.commit()
        
        # Level 4 Elective: Topicsmaster
        db.session.add(LevelRole(level=4, role='Topicsmaster', type='elective', count_required=1, band=1))
        
        tm_sm_role = MeetingRole(name='Topicsmaster', type='standard', needs_approval=False, has_single_owner=True)
        db.session.add(tm_sm_role)
        db.session.commit()

        self.st_tm_sm = SessionType(Title='Topicsmaster', role_id=tm_sm_role.id)
        db.session.add(self.st_tm_sm)
        db.session.commit()

        self.contact = Contact(Name="Kyle Wei", Type="Member")
        db.session.add(self.contact)
        db.session.commit()

        self.meeting = Meeting(Meeting_Number=967, Meeting_Date=date.today(), club_id=self.club.id, status='not started')
        db.session.add(self.meeting)
        db.session.commit()

    def test_waitlist_elective_shows_in_roadmap(self):
        # Create a waitlist log for Topicsmaster
        log = SessionLog(
            Meeting_Number=967, 
            Type_ID=self.st_tm_sm.id, 
            owners=[self.contact], 
            Status='Pending', # Waitlist roles are usually 'Pending' in DB
            state='active'
        )
        # Manually set attributes used by _calculate_completion_summary
        log.session_type = self.st_tm_sm
        log.meeting = self.meeting
        log.is_waitlist = True # This is what matters
        
        # Grouped logs simulation
        grouped_logs = {'4': [log]}
        
        summary = _calculate_completion_summary(grouped_logs, {})
        
        # Check level 4 electives
        l4_electives = summary['4']['elective']
        
        # CURRENT BEHAVIOR: This fails because l4_electives is empty
        self.assertTrue(len(l4_electives) > 0, "Elective roles with waitlist should show up in roadmap")
        
        tm_elective = next((e for e in l4_electives if e['role'] == 'Topicsmaster'), None)
        self.assertIsNotNone(tm_elective, "Topicsmaster should be in the elective list")
        self.assertEqual(tm_elective['status'], 'waitlist', "Topicsmaster status should be 'waitlist'")

if __name__ == '__main__':
    unittest.main()
