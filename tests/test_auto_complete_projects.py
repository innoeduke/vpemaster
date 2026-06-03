import unittest
import sys
import os
from datetime import date

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Meeting, Contact, SessionType, SessionLog, Project, Pathway, PathwayProject
from app.models.roster import MeetingRole
from app.constants import ProjectID
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    LOGIN_DISABLED = True

class TestAutoCompleteProjects(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.client = self.app.test_client()
        self.setup_data()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def setup_data(self):
        # Create Club
        from app.models import Club
        self.club = Club(club_no='123456', club_name='Test Club')
        db.session.add(self.club)
        db.session.flush()

        # Create pathways
        self.pathway = Pathway(name="Presentation Mastery", abbr="PM", status="active", type="pathway")
        db.session.add(self.pathway)
        db.session.flush()

        # Create contact
        self.contact = Contact(Name="John Doe", Type="Member", Current_Path="Presentation Mastery")
        db.session.add(self.contact)
        db.session.flush()

        # Create Project
        self.project = Project(Project_Name="Ice Breaker", Format="Prepared Speech")
        db.session.add(self.project)
        db.session.flush()

        self.pathway_project = PathwayProject(path_id=self.pathway.id, project_id=self.project.id, level=1, code="1.1", type="required")
        db.session.add(self.pathway_project)
        db.session.flush()

        # Create role
        self.role = MeetingRole(name="Prepared Speaker", type="standard", needs_approval=False, has_single_owner=True)
        db.session.add(self.role)
        db.session.flush()

        # Create Session Type
        self.st = SessionType(Title="Prepared Speech", role_id=self.role.id, club_id=self.club.id, Valid_for_Project=True)
        db.session.add(self.st)
        db.session.flush()

        # Create meeting (status: running)
        self.meeting = Meeting(club_id=self.club.id, Meeting_Number=9000, status='running', Meeting_Date=date(2026, 5, 26))
        db.session.add(self.meeting)
        db.session.flush()

        # Create Session Log (project speech)
        self.log = SessionLog(
            meeting_id=self.meeting.id,
            Type_ID=self.st.id,
            Project_ID=self.project.id,
            Status="booked",
            Session_Title="My First Speech",
            pathway="Presentation Mastery"
        )
        db.session.add(self.log)
        db.session.flush()

        # Create Owner record
        from app.models.session import OwnerMeetingRoles
        self.omr = OwnerMeetingRoles(
            meeting_id=self.meeting.id,
            role_id=self.role.id,
            contact_id=self.contact.id,
            session_log_id=self.log.id,
            target_pathway="Presentation Mastery",
            target_level="1"
        )
        db.session.add(self.omr)
        
        # Add Guest Role and Permission for authorized_club_required and AGENDA_VIEW
        from app.models import Permission, AuthRole as Role
        from app.auth.permissions import Permissions
        
        perm_view = Permission(name=Permissions.ABOUT_CLUB_VIEW, description="View Club")
        perm_agenda = Permission(name=Permissions.AGENDA_VIEW, description="View Agenda")
        perm_edit = Permission(name=Permissions.AGENDA_EDIT, description="Edit Agenda")
        role = Role(name='Guest', description='Guest')
        role.permissions.extend([perm_view, perm_agenda, perm_edit])
        db.session.add_all([perm_view, perm_agenda, perm_edit, role])
        
        db.session.commit()
        from app.utils import sync_contact_metadata
        sync_contact_metadata(self.contact.id)
        db.session.refresh(self.contact)

    def test_auto_complete_projects_when_meeting_finished(self):
        """Test that when a meeting is set to finished, its projects are completed and owner metadata synced."""
        # 1. Assert speech log is initially 'booked'
        self.assertEqual(self.log.Status, 'booked')
        self.assertEqual(self.contact.Next_Project, 'PM1.1')

        # 2. Simulate setting meeting to finished via the endpoint
        with self.client.session_transaction() as sess:
            sess['current_club_id'] = self.club.id

        response = self.client.post(f'/agenda/status/{self.meeting.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json.get('new_status'), 'finished')

        # 3. Reload log and contact from database
        db.session.expire_all()
        updated_log = db.session.get(SessionLog, self.log.id)
        updated_contact = db.session.get(Contact, self.contact.id)

        # 4. Verify log status has changed to 'Completed'
        self.assertEqual(updated_log.Status, 'Completed')

        # 5. Verify contact metadata (Next_Project) is updated because of completion sync
        # Since PM1.1 was completed, Next_Project should be recalculated (e.g. to None or the next project in PM level 1 if seeded, but since we didn't seed more projects, it should be None)
        self.assertNotEqual(updated_contact.Next_Project, 'PM1.1')

if __name__ == '__main__':
    unittest.main()
