import sys
import os
import unittest
from datetime import date

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Club, Contact, UserClub, ContactClub, AuthRole, Permission, Pathway, ContactPath, SessionLog
from app.auth.permissions import Permissions
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_ENGINE_OPTIONS = {}

class ContactPathsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Reset session config that conftest may have changed
        db.session.configure(expire_on_commit=True)

        # Seed Pathways
        self.pathway_pm = Pathway(name="Presentation Mastery", abbr="PM", status="active", type="pathway")
        self.pathway_dl = Pathway(name="Dynamic Leadership", abbr="DL", status="active", type="pathway")
        self.pathway_eh = Pathway(name="Engaging Humor", abbr="EH", status="active", type="pathway")
        db.session.add_all([self.pathway_pm, self.pathway_dl, self.pathway_eh])
        
        # Seed Roles and Permissions
        self.role_club_admin = AuthRole(name="ClubAdmin", level=4)
        self.role_member = AuthRole(name="Member", level=1)
        
        self.perm_ach_edit = Permission(name=Permissions.SPEECH_LOGS_MANAGE, description="Edit Achievements")
        self.perm_ach_view = Permission(name=Permissions.LIBRARY_VIEW, description="View Achievements")
        self.perm_cb_edit = Permission(name=Permissions.ROSTER_EDIT, description="Edit Contact Book")
        
        self.role_club_admin.permissions.extend([self.perm_ach_edit, self.perm_cb_edit, self.perm_ach_view])
        self.role_member.permissions.append(self.perm_ach_view)
        
        db.session.add_all([self.role_club_admin, self.role_member, self.perm_ach_edit, self.perm_ach_view, self.perm_cb_edit])
        
        # Create Club
        self.club = Club(club_name="Test Club", club_no="123456")
        db.session.add(self.club)
        db.session.commit()

        # Re-read IDs after commit (since expire_on_commit=True)
        db.session.refresh(self.pathway_pm)
        db.session.refresh(self.pathway_dl)
        db.session.refresh(self.pathway_eh)
        db.session.refresh(self.club)

        # Create Client
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def create_user(self, username, role_name):
        c = Contact(Name=username, Email=f"{username}@example.com", Type='Member')
        db.session.add(c)
        db.session.flush()
        
        u = User(username=username, email=f"{username}@example.com", status='active')
        u.set_password('password')
        db.session.add(u)
        db.session.flush()
        
        role = AuthRole.query.filter_by(name=role_name).first()
        uc = UserClub(user_id=u.id, club_id=self.club.id, contact_id=c.id, is_home=True, auth_role_id=role.id if role else None)
        db.session.add(uc)
        db.session.commit()
        
        # Re-read after commit
        db.session.refresh(u)
        db.session.refresh(c)
        return u, c

    def login(self, username):
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data=dict(
            username=username,
            password='password',
            club_names=str(self.club.id)
        ), follow_redirects=True)
        with self.client.session_transaction() as sess:
            sess['club_id'] = self.club.id
            sess['current_club_id'] = self.club.id

    def test_model_properties_sync(self):
        # Create a contact
        contact = Contact(Name="John Doe", Type="Member")
        db.session.add(contact)
        db.session.commit()
        db.session.refresh(contact)

        # Set Current_Path property (setter should register path as working and default)
        contact.Current_Path = "Presentation Mastery"
        db.session.commit()

        # Verify contact paths table record
        db.session.refresh(contact)
        cp = ContactPath.query.filter_by(contact_id=contact.id).first()
        self.assertIsNotNone(cp)
        self.assertEqual(cp.path_id, self.pathway_pm.id)
        self.assertEqual(cp.status, 'working')
        self.assertTrue(cp.is_default)
        self.assertEqual(contact.Current_Path, "Presentation Mastery")

        # Set Completed_Paths property
        contact.Completed_Paths = "DL5"
        db.session.commit()

        # Verify completed pathways registered
        db.session.refresh(contact)
        cps = ContactPath.query.filter_by(contact_id=contact.id).all()
        self.assertEqual(len(cps), 2)
        
        dl_cp = next(x for x in cps if x.path_id == self.pathway_dl.id)
        self.assertEqual(dl_cp.status, 'completed')
        self.assertFalse(dl_cp.is_default)
        self.assertEqual(contact.Completed_Paths, "DL5")

    def test_api_routes_permissions(self):
        """Test pathway API routes with permission enforcement."""
        admin_user, admin_contact = self.create_user("admin", "ClubAdmin")
        member_user, member_contact = self.create_user("member", "Member")
        
        # Save IDs since objects may become expired/detached
        member_contact_id = member_contact.id
        pm_id = self.pathway_pm.id
        dl_id = self.pathway_dl.id
        
        # --- Test 1: List paths (requires CONTACT_BOOK_EDIT or ACHIEVEMENTS_VIEW) ---
        self.login("member")
        res = self.client.get(f'/api/contacts/{member_contact_id}/pathways')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['registered']), 0)
        self.assertEqual(len(data['available']), 3)

        # --- Test 2: Register path (requires ACHIEVEMENTS_EDIT) ---
        # Member lacks ACHIEVEMENTS_EDIT -> should be 403
        res = self.client.post(
            f'/api/contacts/{member_contact_id}/pathways/register',
            json={'pathway_id': pm_id}
        )
        self.assertEqual(res.status_code, 403)

        # Login as Admin (has ACHIEVEMENTS_EDIT)
        self.login("admin")
        res = self.client.post(
            f'/api/contacts/{member_contact_id}/pathways/register',
            json={'pathway_id': pm_id}
        )
        self.assertEqual(res.status_code, 200)
        
        # Verify via list API
        res = self.client.get(f'/api/contacts/{member_contact_id}/pathways')
        data = res.get_json()
        self.assertEqual(len(data['registered']), 1)
        self.assertEqual(data['registered'][0]['path_id'], pm_id)
        self.assertEqual(data['registered'][0]['status'], 'working')
        self.assertTrue(data['registered'][0]['is_default'])

        # --- Test 3: Register second + Set Default Pathway (requires CONTACT_BOOK_EDIT) ---
        res = self.client.post(
            f'/api/contacts/{member_contact_id}/pathways/register',
            json={'pathway_id': dl_id}
        )
        self.assertEqual(res.status_code, 200)

        # Change default to DL
        res = self.client.post(f'/api/contacts/{member_contact_id}/pathways/{dl_id}/set_default')
        self.assertEqual(res.status_code, 200)
        
        # Verify via list API
        res = self.client.get(f'/api/contacts/{member_contact_id}/pathways')
        data = res.get_json()
        registered = {r['path_id']: r for r in data['registered']}
        self.assertFalse(registered[pm_id]['is_default'])
        self.assertTrue(registered[dl_id]['is_default'])

        # --- Test 4: Complete Pathway ---
        res = self.client.post(f'/api/contacts/{member_contact_id}/pathways/{pm_id}/complete')
        self.assertEqual(res.status_code, 200)
        
        # Verify via list API
        res = self.client.get(f'/api/contacts/{member_contact_id}/pathways')
        data = res.get_json()
        registered = {r['path_id']: r for r in data['registered']}
        self.assertEqual(registered[pm_id]['status'], 'completed')

        # --- Test 5: Deregister Pathway ---
        res = self.client.post(f'/api/contacts/{member_contact_id}/pathways/{pm_id}/deregister')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        
        # Verify via list API
        res = self.client.get(f'/api/contacts/{member_contact_id}/pathways')
        data = res.get_json()
        registered_path_ids = [r['path_id'] for r in data['registered']]
        self.assertNotIn(pm_id, registered_path_ids)
        # DL should still be there
        self.assertIn(dl_id, registered_path_ids)

    def test_migrate_contact_paths_session_logs(self):
        from app.models import SessionLog, SessionType, Meeting, Project
        from scripts.migrate_contact_paths import migrate_data

        # Create a Project
        project = Project(Project_Name="Ice Breaker", Format="Prepared Speech")
        db.session.add(project)
        db.session.flush()

        # Create a session type
        st = SessionType(Title="Prepared Speech", Valid_for_Project=True)
        db.session.add(st)
        db.session.flush()

        # Create a meeting
        m = Meeting(Meeting_Number=101, status='not started', club_id=self.club.id)
        db.session.add(m)
        db.session.flush()

        # Create SessionLog 1: has Project_ID and pathway
        log1 = SessionLog(
            meeting_id=m.id,
            Type_ID=st.id,
            Project_ID=project.id,
            pathway="Presentation Mastery"
        )
        # Create SessionLog 2: has no Project_ID but has pathway
        log2 = SessionLog(
            meeting_id=m.id,
            Type_ID=st.id,
            Project_ID=None,
            pathway="Presentation Mastery"
        )
        db.session.add_all([log1, log2])
        db.session.commit()

        # Run migration
        migrate_data()

        # Refresh from database
        db.session.refresh(log1)
        db.session.refresh(log2)

        # Assertions
        self.assertEqual(log1.pathway, "Presentation Mastery")
        self.assertIsNone(log2.pathway)

    def test_migrate_owner_roles(self):
        from app.models import OwnerMeetingRoles, Meeting, Contact, ContactPath
        from scripts.migrate_owner_meeting_roles import migrate_owner_roles

        # 1. Create a contact with a registered pathway and current path
        c1 = Contact(Name="Alice Member", Type="Member", credentials="PM3")
        db.session.add(c1)
        db.session.flush()

        # Add registered path for Alice
        cp1 = ContactPath(
            contact_id=c1.id,
            path_id=self.pathway_pm.id,
            status='working',
            is_default=True,
            registered_date=date(2026, 1, 1)
        )
        db.session.add(cp1)
        db.session.flush()

        # Update contact current path
        c1.Current_Path = "Presentation Mastery"
        db.session.commit()

        # 2. Create a meeting
        m = Meeting(Meeting_Number=102, status='not started', club_id=self.club.id, Meeting_Date=date(2026, 2, 1))
        db.session.add(m)
        db.session.flush()

        # 3. Create OwnerMeetingRoles entry without target_pathway / target_level
        omr = OwnerMeetingRoles(
            meeting_id=m.id,
            contact_id=c1.id,
            target_pathway=None,
            target_level=None
        )
        db.session.add(omr)
        db.session.commit()

        # 4. Run migrate_owner_roles
        migrate_owner_roles()

        # 5. Refresh and verify
        db.session.refresh(omr)
        self.assertEqual(omr.target_pathway, "Presentation Mastery")
        # active level for Alice at the time (no achievements yet) should be L1
        self.assertEqual(omr.target_level, "1")

if __name__ == '__main__':
    unittest.main()
