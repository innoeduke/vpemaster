import unittest
import sys
import app
print(f"DEBUG: app type: {type(app)}")
print(f"DEBUG: app file: {getattr(app, '__file__', 'no file')}")
print(f"DEBUG: app path: {getattr(app, '__path__', 'no path')}")
from app.models import LevelRole, SessionLog, Contact, Meeting, SessionType, MeetingRole, Project
from app import create_app, db
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
            LevelRole(level=1, role='Toastmaster', type='required', count_required=1, band=0),
            # Elective Pool removed, using band=1 for electives
            LevelRole(level=1, role='Timer', type='elective', count_required=1, band=1),
            LevelRole(level=1, role='Ah-Counter', type='elective', count_required=1, band=1),
            
            LevelRole(level=4, role='TME', type='required', count_required=1, band=0),
            # Elective Pool removed, using band=1 for electives
            LevelRole(level=4, role='Topicsmaster', type='elective', count_required=1, band=1),
            LevelRole(level=4, role='Topics Speaker', type='elective', count_required=1, band=1),
            LevelRole(level=4, role='Photographer', type='elective', count_required=1, band=1),

            LevelRole(level=5, role='GE', type='required', count_required=2, band=0),
            # Elective Pool removed, using band=1 for electives (Implicit quota handled by logic, usually 2 for L5)
        ])
        
        # Add roles and session types with mandatory fields
        tm_role = MeetingRole(name='Toastmaster', type='standard', needs_approval=False, has_single_owner=True)
        timer_role = MeetingRole(name='Timer', type='standard', needs_approval=False, has_single_owner=True)
        ah_role = MeetingRole(name='Ah-Counter', type='standard', needs_approval=False, has_single_owner=True)
        tme_role = MeetingRole(name='TME', type='standard', needs_approval=False, has_single_owner=True)
        tm_sm_role = MeetingRole(name='Topicsmaster', type='standard', needs_approval=False, has_single_owner=True)
        ts_role = MeetingRole(name='Topics Speaker', type='standard', needs_approval=False, has_single_owner=True)
        ge_role = MeetingRole(name='General Evaluator', type='standard', needs_approval=False, has_single_owner=True)
        db.session.add_all([tm_role, timer_role, ah_role, tme_role, tm_sm_role, ts_role, ge_role])
        db.session.commit()

        self.st_tm = SessionType(Title='Toastmaster', role_id=tm_role.id)
        self.st_timer = SessionType(Title='Timer', role_id=timer_role.id)
        self.st_ah = SessionType(Title='Ah-Counter', role_id=ah_role.id)
        self.st_tme = SessionType(Title='Toastmaster', role_id=tme_role.id)
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
        log1 = SessionLog(Meeting_Number=1, Type_ID=self.st_timer.id, owners=[self.contact], Status='Completed', state='active', project_code='L1-E')
        # Manually set attributes that normally come from joinedload or processing
        log1.session_type = self.st_timer
        log1.log_type = 'role'
        log1.project = None
        
        summary = _calculate_completion_summary({'1': [log1]}, {})
        self.assertEqual(summary['1']['elective_count'], 1)
        self.assertTrue(summary['1']['elective_completed'])

    def test_level4_elective_pool(self):
        # Prevent auto-flush warning when creating transient logs
        with db.session.no_autoflush:
            # Case 1: One elective role completed (L4 need 2)
            log1 = SessionLog(id=1, Meeting_Number=1, Type_ID=self.st_tm_sm.id, owners=[self.contact], Status='Completed', state='active')
            log1.session_type = self.st_tm_sm
            log1.log_type = 'role'
            log1.project = None
            
            summary = _calculate_completion_summary({'4': [log1]}, {})
            self.assertEqual(summary['4']['elective_count'], 1)
            self.assertTrue(summary['4']['elective_completed'])

            # Case 2: Two elective roles completed
            log2 = SessionLog(id=2, Meeting_Number=1, Type_ID=self.st_ts.id, owners=[self.contact], Status='Completed', state='active')
            log2.session_type = self.st_ts
            log2.log_type = 'role'
            log2.project = None
            
            summary = _calculate_completion_summary({'4': [log1, log2]}, {})
            self.assertEqual(summary['4']['elective_count'], 1)
            self.assertTrue(summary['4']['elective_completed'])

    def test_role_matching_strictness(self):
        # L2 IE needs 1 count
        db.session.add(LevelRole(level=2, role='Individual Evaluator', type='required', count_required=1))
        db.session.commit()
        
        # Log 1: GE (should NOT match IE)
        log_ge = SessionLog(id=10, Meeting_Number=1, Type_ID=self.st_ge.id, owners=[self.contact], Status='Completed', state='active', project_code='PM2')
        log_ge.session_type = self.st_ge
        log_ge.log_type = 'role'
        
        # Log 2: IE (should match IE)
        st_ie = SessionType(Title='Individual Evaluator', role_id=self.st_ge.role_id) # Reuse role_id for simplicity or create real one
        log_ie = SessionLog(id=11, Meeting_Number=2, Type_ID=100, owners=[self.contact], Status='Completed', state='active', project_code='PM2')
        log_ie.session_type = SessionType(Title='Individual Evaluator', role=MeetingRole(name='Individual Evaluator', type='standard', needs_approval=False, has_single_owner=True))
        log_ie.log_type = 'role'
        
        summary = _calculate_completion_summary({'2': [log_ge, log_ie]}, {})
        ie_req = next(r for r in summary['2']['required'] if r['role'] == 'Individual Evaluator')
        self.assertEqual(ie_req['count'], 1)
        self.assertEqual(len(ie_req['requirement_items']), 1)
        self.assertEqual(ie_req['requirement_items'][0]['status'], 'completed')
        self.assertEqual(ie_req['requirement_items'][0]['name'], 'Individual Evaluator')

    def test_level5_required_roles(self):
        # L5 GE needs 2 counts
        log1 = SessionLog(id=3, Meeting_Number=1, Type_ID=self.st_ge.id, owners=[self.contact], Status='Completed', state='active')
        log1.session_type = self.st_ge
        log1.log_type = 'role'
        log1.project = None
        
        log2 = SessionLog(id=4, Meeting_Number=2, Type_ID=self.st_ge.id, owners=[self.contact], Status='Completed', state='active')
        log2.session_type = self.st_ge
        log2.log_type = 'role'
        log2.project = None

        log3 = SessionLog(id=5, Meeting_Number=3, Type_ID=self.st_ge.id, owners=[self.contact], Status='Completed', state='active')
        log3.session_type = self.st_ge
        log3.log_type = 'role'
        log3.project = None
        
        # Test capping: 3 logs for a 2-count requirement should only show 2 dots
        summary = _calculate_completion_summary({'5': [log1, log2, log3]}, {})
        ge_req = next(r for r in summary['5']['required'] if r['role'] == 'GE')
        self.assertEqual(ge_req['count'], 3)
        self.assertEqual(len(ge_req['requirement_items']), 2)
        self.assertTrue(summary['5']['required_completed'])

    def test_speech_requirements(self):
        from app.models import Pathway, PathwayProject, Project
        # Seed pathway and projects
        pm_path = Pathway(name='Presentation Mastery', abbr='PM', type='pathway')
        db.session.add(pm_path)
        db.session.commit()
        
        p1 = Project(Project_Name='Ice Breaker', Format='Prepared Speech')
        db.session.add(p1)
        db.session.commit()
        
        pp1 = PathwayProject(path_id=pm_path.id, project_id=p1.id, code='1.1', level=1, type='required')
        db.session.add(pp1)
        db.session.commit()
        
        # Log for this project
        log1 = SessionLog(id=20, Meeting_Number=1, Type_ID=self.st_ge.id, owners=[self.contact], 
                          Status='Completed', Project_ID=p1.id, state='active')
        log1.project = p1
        log1.meeting = self.meeting
        log1.session_type = self.st_ge
        
        # Test summary with pathway context
        summary = _calculate_completion_summary({'1': [log1]}, {}, selected_pathway_name='Presentation Mastery')
        
        self.assertIn('speeches', summary['1'])
        self.assertEqual(len(summary['1']['speeches']), 1)
        self.assertEqual(summary['1']['speeches'][0]['project_code'], '1.1')
        self.assertEqual(summary['1']['speeches'][0]['status'], 'completed')
        self.assertEqual(len(summary['1']['speeches'][0]['history_items']), 1)
        self.assertEqual(summary['1']['speeches'][0]['history_items'][0]['meeting_number'], 1)

    def test_extra_speech_filtering(self):
        from app.models import Project
        
        # Create an "Extra" prepared speech (not in required list)
        # Fix: Ensure Format is set correctly so is_prepared_speech property works
        p_extra = Project(Project_Name='Extra Speech', Format='Prepared Speech')
        db.session.add(p_extra)
        db.session.commit()
        
        # Log for this extra speech
        log_extra = SessionLog(id=30, Meeting_Number=2, Type_ID=self.st_ge.id, owners=[self.contact], 
                               Status='Completed', Project_ID=p_extra.id, state='active')
        log_extra.project = p_extra # Manually attach for test environment
        log_extra.meeting = self.meeting
        log_extra.session_type = self.st_ge
        
        # Run summary
        summary = _calculate_completion_summary({'1': [log_extra]}, {})
        
        # Verify it is NOT in extra_roles because it's a prepared speech
        extra_roles = summary['1'].get('extra_roles', [])
        self.assertEqual(len(extra_roles), 0, f"Expected 0 extra roles, found: {extra_roles}")

    def test_elective_speech_logic(self):
        from app.models import Pathway, PathwayProject, Project
        from app.utils import get_level_project_requirements
        
        # 1. Setup Pathway "Visionary Comms"
        vc_path = Pathway(name='Visionary Communication', abbr='VC', type='pathway')
        db.session.add(vc_path)
        db.session.commit()
        
        # 2. Setup Level 3 Electives (requirement is usually 2 electives)
        # Mockutils: We rely on real utils.py but we can verify assumption or mock if needed.
        # Assuming Level 3 requires 2 electives (standard TM logic)
        
        p_elec1 = Project(Project_Name='Storytelling', Format='Elective')
        p_elec2 = Project(Project_Name='Sense of Humor', Format='Elective')
        db.session.add_all([p_elec1, p_elec2])
        db.session.commit()
        
        pp_e1 = PathwayProject(path_id=vc_path.id, project_id=p_elec1.id, code='L3-E', level=3, type='elective')
        pp_e2 = PathwayProject(path_id=vc_path.id, project_id=p_elec2.id, code='L3-E', level=3, type='elective')
        db.session.add_all([pp_e1, pp_e2])
        
        # Add a LevelRole for Level 3 so it gets processed
        lr3 = LevelRole(level=3, role='Toastmaster', type='required', count_required=1, band=0)
        db.session.add(lr3)
        db.session.commit()
        
        # Create a generic Speaker role/session type to avoid matching 'Toastmaster' requirement
        from app.models import MeetingRole, SessionType
        r_spk = MeetingRole(name='Speaker', type='standard', needs_approval=False, has_single_owner=True)
        db.session.add(r_spk)
        db.session.commit()
        st_spk = SessionType(Title='Prepared Speech', role_id=r_spk.id)
        db.session.add(st_spk)
        db.session.commit()

        # 3. Log ONE completed elective
        log_e1 = SessionLog(id=40, Meeting_Number=3, Type_ID=st_spk.id, owners=[self.contact],
                            Status='Completed', Project_ID=p_elec1.id, state='active')
        log_e1.project = p_elec1
        log_e1.meeting = self.meeting
        log_e1.session_type = st_spk
        
        # 4. Run summary for Level 3
        # Use existing get_level_project_requirements to verify assumptions first
        reqs = get_level_project_requirements()
        l3_reqs = reqs.get(3, {})
        elective_count_needed = l3_reqs.get('elective_count', 2) # Default to 2 if not found
        
        summary = _calculate_completion_summary({'3': [log_e1]}, {}, selected_pathway_name='Visionary Communication')
        
        speeches = summary['3'].get('speeches', [])
        
        # Should have exactly ONE speech entry for the electives (consolidated badge)
        self.assertEqual(len(speeches), 1)
        
        badge = speeches[0]
        self.assertEqual(badge['project_code'], '3.2')
        # Status should be pending because 1 out of 2 are done
        self.assertEqual(badge['status'], 'pending')
        
        # Verify requirement items (dots)
        req_items = badge['requirement_items']
        self.assertEqual(len(req_items), elective_count_needed) # Should be 2
        
        # First dot: Completed
        self.assertEqual(req_items[0]['status'], 'completed')
        self.assertIn('Storytelling', req_items[0]['name'])
        
        # Second dot: Pending
        if elective_count_needed > 1:
            self.assertEqual(req_items[1]['status'], 'pending')
            self.assertEqual(req_items[1]['name'], 'Pending Elective')
            
        # Verify history items
        self.assertEqual(len(badge['history_items']), 1)
        self.assertIn('Storytelling', badge['history_items'][0]['name'])

    def test_subproject_consolidation(self):
        from app.models import Pathway, PathwayProject, Project, MeetingRole, SessionType
        
        # 1. Setup Pathway "Innovative Planning"
        ip_path = Pathway(name='Innovative Planning', abbr='IP', type='pathway')
        db.session.add(ip_path)
        db.session.commit()
        
        # 2. Setup Level 1 Required Projects with Sub-projects
        # 1.4.1 and 1.4.2
        p_sub1 = Project(Project_Name='Research', Format='Prepared Speech')
        p_sub2 = Project(Project_Name='Present', Format='Prepared Speech')
        db.session.add_all([p_sub1, p_sub2])
        db.session.commit()
        
        pp_sub1 = PathwayProject(path_id=ip_path.id, project_id=p_sub1.id, code='1.4.1', level=1, type='required')
        pp_sub2 = PathwayProject(path_id=ip_path.id, project_id=p_sub2.id, code='1.4.2', level=1, type='required')
        db.session.add_all([pp_sub1, pp_sub2])
        
        # Add a LevelRole so Level 1 is processed
        lr1 = LevelRole(level=1, role='Toastmaster', type='required', count_required=1, band=0)
        db.session.add(lr1)
        db.session.commit()
        
        # 3. Log ONE completed sub-project (1.4.1)
        # Use simple session/role setup
        # Reuse Speaker role if existing or create new
        r_spk = MeetingRole.query.filter_by(name='Speaker').first()
        if not r_spk:
            r_spk = MeetingRole(name='Speaker', type='standard', needs_approval=False, has_single_owner=True)
            db.session.add(r_spk)
            db.session.commit()
            
        st_spk = SessionType.query.filter_by(role_id=r_spk.id).first()
        if not st_spk:
            st_spk = SessionType(Title='Prepared Speech', role_id=r_spk.id)
            db.session.add(st_spk)
            db.session.commit()
            
        log_s1 = SessionLog(id=50, Meeting_Number=3, Type_ID=st_spk.id, owners=[self.contact],
                            Status='Completed', Project_ID=p_sub1.id, state='active')
        log_s1.project = p_sub1
        log_s1.meeting = self.meeting
        log_s1.session_type = st_spk
        
        # 4. Run summary
        summary = _calculate_completion_summary({'1': [log_s1]}, {}, selected_pathway_name='Innovative Planning')
        
        speeches = summary['1'].get('speeches', [])
        
        # Should have ONE badge for '1.4'
        # Iterate to find it in case other standard Level 1 projects (1.1, 1.2, 1.3) were auto-added by assumptions?
        # In this test setup, only 1.4.1 and 1.4.2 are added to the pathway. 
        # So speeches list should likely only contain '1.4'.
        
        self.assertEqual(len(speeches), 1)
        badge = speeches[0]
        
        self.assertEqual(badge['project_code'], '1.4')
        self.assertEqual(badge['status'], 'pending') # Only 1 of 2 done
        
        # Requirement items (dots) should correspond to the 2 sub-projects
        req_items = badge['requirement_items']
        self.assertEqual(len(req_items), 2)
        
        # 1.4.1 should be completed
        self.assertEqual(req_items[0]['status'], 'completed')
        self.assertIn('1.4.1', req_items[0]['name'])
        
        # 1.4.2 should be pending
        self.assertEqual(req_items[1]['status'], 'pending')
        self.assertIn('1.4.2', req_items[1]['name'])

    def test_history_details(self):
        """Verify new history fields: full code, title, evaluator, media_url"""
        from app.models import PathwayProject, Project, MeetingRole, SessionType, Media
        
        # 1. Setup
        p1 = Project(Project_Name='Ice Breaker', Format='Prepared Speech')
        db.session.add(p1)
        db.session.commit()
        
        # Link to pathway
        vc_path = self.st_tm.role.contacts[0].pathway_obj # Assuming setup created a pathway
        # Logic relies on valid PathwayProject for code derivation
        pp1 = PathwayProject(path_id=vc_path.id, project_id=p1.id, code='1.1', level=1, type='required')
        db.session.add(pp1)
        db.session.commit()
        
        # 2. Create Roles: Speaker 1 and Evaluator 1
        r_spk1 = MeetingRole(name='Speaker 1', type='standard', needs_approval=False, has_single_owner=True)
        r_eval1 = MeetingRole(name='Evaluator 1', type='standard', needs_approval=False, has_single_owner=True)
        db.session.add_all([r_spk1, r_eval1])
        db.session.commit()
        
        st_spk1 = SessionType(Title='Prepared Speech', role_id=r_spk1.id)
        st_eval1 = SessionType(Title='Evaluation', role_id=r_eval1.id)
        db.session.add_all([st_spk1, st_eval1])
        db.session.commit()
        
        # 3. Log Speaker 1 (The User)
        log_s1 = SessionLog(id=60, Meeting_Number=5, Type_ID=st_spk1.id, owners=[self.contact],
                            Status='Completed', Project_ID=p1.id, state='active', Session_Title="My First Speech")
        log_s1.project = p1
        log_s1.meeting = self.meeting
        log_s1.session_type = st_spk1
        # Add media
        log_s1.media = Media(url="http://video.link")
        # Ensure project code is set
        log_s1.project_code = "VC1.1" # Pre-calculated usually
        
        # 4. Log Evaluator 1 (Another User)
        # We need another contact for evaluator
        evaluator_contact = Contact(Name="Eval Person", Primary_Email="eval@test.com")
        db.session.add(evaluator_contact)
        db.session.commit()
        
        log_e1 = SessionLog(id=61, Meeting_Number=5, Type_ID=st_eval1.id, owners=[evaluator_contact],
                            Status='Completed', state='active')
        log_e1.meeting = self.meeting
        log_e1.session_type = st_eval1
        
        # 5. Run Summary
        summary = _calculate_completion_summary({'1': [log_s1]}, {}, selected_pathway_name='Visionary Communication')
        speeches = summary['1'].get('speeches', [])
        
        # Find the speech
        badge = next((s for s in speeches if s['project_code'] == '1.1'), None)
        self.assertIsNotNone(badge)
        
        history = badge['history_items'][0]
        
        # Verify New Fields
        self.assertEqual(history['project_code'], 'VC1.1')
        self.assertEqual(history['speech_title'], 'My First Speech')
        self.assertEqual(history['media_url'], 'http://video.link')
        self.assertEqual(history['evaluator'], 'Eval Person')

        self.assertEqual(history['evaluator'], 'Eval Person')

    def test_speech_without_explicit_pathway(self):
        """Verify speech logs without explicit pathway but valid project are included."""
        from app.models import PathwayProject, Project, MeetingRole, SessionType, Pathway
        
        # 1. Setup Pathway and Project
        # Use existing 'Innovative Planning' from setUp or create new
        ip_path = Pathway.query.filter_by(name='Innovative Planning').first()
        if not ip_path:
            ip_path = Pathway(name='Innovative Planning', abbr='IP', type='pathway')
            db.session.add(ip_path)
            db.session.commit()
            
        p1 = Project(Project_Name='Generic Project', Format='Prepared Speech')
        db.session.add(p1)
        db.session.commit()
        
        # Link Project to Pathway
        pp1 = PathwayProject(path_id=ip_path.id, project_id=p1.id, code='1.1', level=1, type='required')
        db.session.add(pp1)
        db.session.commit()
        
        # 2. Level Role
        lr1 = LevelRole(level=1, role='Toastmaster', type='required', count_required=1, band=0)
        db.session.add(lr1)
        db.session.commit()
        
        # 3. Log Speech WITHOUT 'pathway' attribute set
        r_spk = MeetingRole.query.filter_by(name='Speaker').first() or MeetingRole(name='Speaker', type='standard', needs_approval=False, has_single_owner=True)
        db.session.add(r_spk)
        db.session.commit()
        st_spk = SessionType.query.filter_by(role_id=r_spk.id).first() or SessionType(Title='Prepared Speech', role_id=r_spk.id)
        db.session.add(st_spk)
        db.session.commit()
        
        log = SessionLog(id=70, Meeting_Number=6, Type_ID=st_spk.id, owners=[self.contact],
                            Status='Completed', Project_ID=p1.id, state='active')
        log.project = p1 # Ensure relationship
        log.meeting = self.meeting
        log.session_type = st_spk
        log.pathway = None # EXPLICITLY NONE
        
        # 4. Run Summary
        # Should be included because project is linked to 'Innovative Planning'
        summary = _calculate_completion_summary({'1': [log]}, {}, selected_pathway_name='Innovative Planning')
        speeches = summary['1'].get('speeches', [])
        
        self.assertEqual(len(speeches), 1)
        self.assertEqual(speeches[0]['project_code'], '1.1')
        self.assertEqual(speeches[0]['status'], 'completed')

if __name__ == '__main__':
    unittest.main()
