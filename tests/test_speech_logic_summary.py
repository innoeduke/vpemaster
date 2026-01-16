import unittest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from app.models import LevelRole, SessionLog, Contact, Meeting, SessionType, MeetingRole, Project
from app.speech_logs_routes import _calculate_completion_summary
from datetime import date

class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test-secret'
    WTF_CSRF_ENABLED = False

class TestSpeechLogicSummary(unittest.TestCase):
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
        # Create a test club first (required for Meeting.club_id)
        from app.models import Club
        self.club = Club(
            club_no='000000',
            club_name='Test Club',
            district='Test District',
            division='Test Division',
            area='Test Area'
        )
        db.session.add(self.club)
        db.session.commit()
        
        # Add LevelRoles (including elective pool)
        db.session.add_all([
            LevelRole(level=1, role='Toastmaster', type='required', count_required=1),
            LevelRole(level=1, role='Elective Pool', type='elective', count_required=1),
            LevelRole(level=1, role='Timer', type='elective', count_required=1),
            LevelRole(level=1, role='Ah-Counter', type='elective', count_required=1),
            
            LevelRole(level=4, role='TME', type='required', count_required=1),
            LevelRole(level=4, role='Elective Pool', type='elective', count_required=2),
            LevelRole(level=4, role='Topicsmaster', type='elective', count_required=1),
            LevelRole(level=4, role='Topics Speaker', type='elective', count_required=1),
            LevelRole(level=4, role='Photographer', type='elective', count_required=1),

            LevelRole(level=5, role='GE', type='required', count_required=2),
            LevelRole(level=5, role='Elective Pool', type='elective', count_required=2),
        ])
        
        # Add roles and session types with mandatory fields
        tm_role = MeetingRole(name='Toastmaster', type='standard', needs_approval=False, is_distinct=True)
        timer_role = MeetingRole(name='Timer', type='standard', needs_approval=False, is_distinct=True)
        ah_role = MeetingRole(name='Ah-Counter', type='standard', needs_approval=False, is_distinct=True)
        tme_role = MeetingRole(name='TME', type='standard', needs_approval=False, is_distinct=True)
        tm_sm_role = MeetingRole(name='Topicsmaster', type='standard', needs_approval=False, is_distinct=True)
        ts_role = MeetingRole(name='Topics Speaker', type='standard', needs_approval=False, is_distinct=True)
        ge_role = MeetingRole(name='General Evaluator', type='standard', needs_approval=False, is_distinct=True)
        db.session.add_all([tm_role, timer_role, ah_role, tme_role, tm_sm_role, ts_role, ge_role])
        db.session.commit()

        self.st_tm = SessionType(Title='Toastmaster', role_id=tm_role.id)
        self.st_timer = SessionType(Title='Timer', role_id=timer_role.id)
        self.st_ah = SessionType(Title='Ah-Counter', role_id=ah_role.id)
        self.st_tme = SessionType(Title='TME', role_id=tme_role.id)
        self.st_tm_sm = SessionType(Title='Topicsmaster', role_id=tm_sm_role.id)
        self.st_ts = SessionType(Title='Topics Speaker', role_id=ts_role.id)
        self.st_ge = SessionType(Title='General Evaluator', role_id=ge_role.id)
        db.session.add_all([self.st_tm, self.st_timer, self.st_ah, self.st_tme, self.st_tm_sm, self.st_ts, self.st_ge])
        db.session.commit()

        self.contact = Contact(Name="Test User", Type="Member")
        db.session.add(self.contact)
        db.session.commit()

        self.meeting = Meeting(Meeting_Number=1, Meeting_Date=date.today(), club_id=self.club.id)
        db.session.add(self.meeting)
        db.session.commit()

    def test_level1_elective_pool(self):
        # Case 1: No logs
        summary = _calculate_completion_summary({}, {})
        self.assertEqual(summary['1']['elective_count'], 0)
        self.assertFalse(summary['1']['elective_completed'])

        # Case 2: One elective role completed (L1 need 1)
        log1 = SessionLog(Meeting_Number=1, Type_ID=self.st_timer.id, Owner_ID=self.contact.id, Status='Completed', state='active', project_code='L1-E')
        # Manually set attributes that normally come from joinedload or processing
        log1.session_type = self.st_timer
        log1.log_type = 'role'
        log1.project = None
        
        summary = _calculate_completion_summary({'1': [log1]}, {})
        self.assertEqual(summary['1']['elective_count'], 1)
        self.assertTrue(summary['1']['elective_completed'])

    def test_level4_elective_pool(self):
        # Case 1: One elective role completed (L4 need 2)
        log1 = SessionLog(id=1, Meeting_Number=1, Type_ID=self.st_tm_sm.id, Owner_ID=self.contact.id, Status='Completed', state='active')
        log1.session_type = self.st_tm_sm
        log1.log_type = 'role'
        log1.project = None
        
        summary = _calculate_completion_summary({'4': [log1]}, {})
        self.assertEqual(summary['4']['elective_count'], 1)
        self.assertFalse(summary['4']['elective_completed'])

        # Case 2: Two elective roles completed
        log2 = SessionLog(id=2, Meeting_Number=1, Type_ID=self.st_ts.id, Owner_ID=self.contact.id, Status='Completed', state='active')
        log2.session_type = self.st_ts
        log2.log_type = 'role'
        log2.project = None
        
        summary = _calculate_completion_summary({'4': [log1, log2]}, {})
        self.assertEqual(summary['4']['elective_count'], 2)
        self.assertTrue(summary['4']['elective_completed'])

    def test_role_matching_strictness(self):
        # L2 IE needs 1 count
        db.session.add(LevelRole(level=2, role='Individual Evaluator', type='required', count_required=1))
        db.session.commit()
        
        # Log 1: GE (should NOT match IE)
        log_ge = SessionLog(id=10, Meeting_Number=1, Type_ID=self.st_ge.id, Owner_ID=self.contact.id, Status='Completed', state='active', project_code='PM2')
        log_ge.session_type = self.st_ge
        log_ge.log_type = 'role'
        
        # Log 2: IE (should match IE)
        st_ie = SessionType(Title='Individual Evaluator', role_id=self.st_ge.role_id) # Reuse role_id for simplicity or create real one
        log_ie = SessionLog(id=11, Meeting_Number=2, Type_ID=100, Owner_ID=self.contact.id, Status='Completed', state='active', project_code='PM2')
        log_ie.session_type = SessionType(Title='Individual Evaluator', role=MeetingRole(name='Individual Evaluator', type='standard', needs_approval=False, is_distinct=True))
        log_ie.log_type = 'role'
        
        summary = _calculate_completion_summary({'2': [log_ge, log_ie]}, {})
        ie_req = next(r for r in summary['2']['required'] if r['role'] == 'Individual Evaluator')
        self.assertEqual(ie_req['count'], 1)
        self.assertEqual(len(ie_req['requirement_items']), 1)
        self.assertEqual(ie_req['requirement_items'][0]['status'], 'completed')
        self.assertEqual(ie_req['requirement_items'][0]['name'], 'PM2 Individual Evaluator')

    def test_level5_required_roles(self):
        # L5 GE needs 2 counts
        log1 = SessionLog(id=3, Meeting_Number=1, Type_ID=self.st_ge.id, Owner_ID=self.contact.id, Status='Completed', state='active')
        log1.session_type = self.st_ge
        log1.log_type = 'role'
        log1.project = None
        
        log2 = SessionLog(id=4, Meeting_Number=2, Type_ID=self.st_ge.id, Owner_ID=self.contact.id, Status='Completed', state='active')
        log2.session_type = self.st_ge
        log2.log_type = 'role'
        log2.project = None

        log3 = SessionLog(id=5, Meeting_Number=3, Type_ID=self.st_ge.id, Owner_ID=self.contact.id, Status='Completed', state='active')
        log3.session_type = self.st_ge
        log3.log_type = 'role'
        log3.project = None
        
        # Test capping: 3 logs for a 2-count requirement should only show 2 dots
        summary = _calculate_completion_summary({'5': [log1, log2, log3]}, {})
        ge_req = next(r for r in summary['5']['required'] if r['role'] == 'GE')
        self.assertEqual(ge_req['count'], 2)
        self.assertEqual(len(ge_req['requirement_items']), 2)
        self.assertTrue(summary['5']['required_completed'])

if __name__ == '__main__':
    unittest.main()
