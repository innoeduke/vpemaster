import unittest
from datetime import date
from app import create_app, db
from app.models import Contact, Meeting, SessionType, SessionLog, MeetingRole, Project, Pathway, PathwayProject
from app.constants import ProjectID

class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test-secret'
    WTF_CSRF_ENABLED = False

class TestTableTopicsProjectLogic(unittest.TestCase):
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
        # 1. Create Pathway and Project
        self.pathway = Pathway(name='Presentation Mastery', abbr='PM', type='pathway', status='active')
        db.session.add(self.pathway)
        db.session.commit()

        self.project_pm1_1 = Project(id=1, Project_Name='Ice Breaker', Format='Prepared Speech')
        self.project_tt = Project(id=10, Project_Name='Active Listening', Format='Table Topics')
        db.session.add_all([self.project_pm1_1, self.project_tt])
        db.session.commit()

        self.pp1 = PathwayProject(path_id=self.pathway.id, project_id=self.project_pm1_1.id, code='1.1', level=1, type='required')
        self.pp_tt = PathwayProject(path_id=self.pathway.id, project_id=self.project_tt.id, code='L1-TT', level=1, type='elective')
        db.session.add_all([self.pp1, self.pp_tt])
        db.session.commit()

        # 2. Create Roles and SessionTypes
        self.tt_role = MeetingRole(name='Topicsmaster', type='standard', has_single_owner=True, needs_approval=False)
        self.speaker_role = MeetingRole(name='Prepared Speaker', type='standard', has_single_owner=True, needs_approval=False)
        db.session.add_all([self.tt_role, self.speaker_role])
        db.session.commit()

        self.st_tt = SessionType(Title='Table Topics', role_id=self.tt_role.id, Valid_for_Project=True)
        self.st_speech = SessionType(Title='Prepared Speech', role_id=self.speaker_role.id, Valid_for_Project=True)
        db.session.add_all([self.st_tt, self.st_speech])
        db.session.commit()

        # 3. Create Contact with Next_Project
        self.contact = Contact(Name="Kyle", Type="Member", Current_Path="Presentation Mastery", Next_Project="PM1.1")
        db.session.add(self.contact)
        db.session.commit()

        # 4. Create Meeting
        self.meeting = Meeting(Meeting_Number=1, Meeting_Date=date.today(), club_id=1)
        db.session.add(self.meeting)
        db.session.commit()

    def test_reproduction_table_topics_auto_resolve(self):
        """
        FAILING TEST: Assigning Kyle (who has PM1.1 as Next_Project) to Table Topics
        should NOT auto-resolve to PM1.1.
        """
        # Create a Table Topics log
        log = SessionLog(meeting_id=self.meeting.id, Type_ID=self.st_tt.id, Meeting_Seq=1)
        db.session.add(log)
        db.session.commit()

        # Assign Kyle using SessionLog.set_owners (or RoleService if we want to be more realistic, but set_owners is the direct target)
        SessionLog.set_owners(log, [self.contact.id])
        db.session.commit()

        # REPRODUCTION: After setting owners, log.Project_ID should NOT be populated with Kyle's Next_Project (1)
        # CURRENT BEHAVIOR (suspected): It is populated because Table Topics is in SPEECH_TYPES_WITH_PROJECT (indirectly via Valid_for_Project check)
        
        print(f"DEBUG: log.Project_ID = {log.Project_ID}")
        print(f"DEBUG: log.project_code = {log.project_code}")
        
        # We WANT it to be None, but it probably is 1 (Ice Breaker)
        self.assertIsNone(log.Project_ID, "Table Topics should NOT automatically inherit owner's Next_Project")
        self.assertIsNone(log.project_code, "Table Topics should NOT have a project code unless assigned")

    def test_speech_auto_resolve(self):
        """
        SUCCESS TEST: Prepared Speech SHOULD still auto-resolve to Kyle's Next_Project.
        """
        log = SessionLog(meeting_id=self.meeting.id, Type_ID=self.st_speech.id, Meeting_Seq=2)
        db.session.add(log)
        db.session.commit()

        SessionLog.set_owners(log, [self.contact.id])
        db.session.commit()

        self.assertEqual(log.Project_ID, 1, "Prepared Speech SHOULD inherit owner's Next_Project")
        self.assertEqual(log.project_code, "PM1.1")

if __name__ == '__main__':
    unittest.main()
