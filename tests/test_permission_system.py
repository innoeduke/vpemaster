import unittest
import sys
import os
from datetime import date

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Contact, Permission, AuthRole, Meeting
from app.auth.permissions import Permissions
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class PermissionSystemTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        self.client = self.app.test_client()
        self.setup_permissions()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def setup_permissions(self):
        # 1. Create permissions
        self.perm_view = Permission(name=Permissions.AGENDA_VIEW, description="View Agenda")
        self.perm_edit = Permission(name=Permissions.AGENDA_EDIT, description="Edit Agenda")
        db.session.add_all([self.perm_view, self.perm_edit])
        
        # 2. Create roles
        self.role_admin = AuthRole(name="SysAdmin", description="Admin Role", level=10)
        self.role_user = AuthRole(name="User", description="User Role", level=1)
        self.role_guest = AuthRole(name="Guest", description="Guest Role", level=0)
        db.session.add_all([self.role_admin, self.role_user, self.role_guest])
        db.session.flush()
        
        # 3. Assign permissions to roles
        self.role_admin.permissions.append(self.perm_view)
        self.role_admin.permissions.append(self.perm_edit)
        self.role_user.permissions.append(self.perm_view)
        self.role_guest.permissions.append(self.perm_view)
        
        # 4. Create users
        self.contact_admin = Contact(Name="Admin User")
        self.contact_user = Contact(Name="Standard User")
        db.session.add_all([self.contact_admin, self.contact_user])
        db.session.flush()
        
        self.user_admin = User(username="admin", email="admin@test.com")
        self.user_admin.set_password("password")
        
        self.user_user = User(username="user", email="user@test.com")
        self.user_user.set_password("password")
        
        db.session.add_all([self.user_admin, self.user_user])
        
        # Create Club (required for Meeting)
        from app.models import Club, UserClub
        self.club = Club(
            club_no='000000',
            club_name='Test Club',
            district='Test District'
        )
        db.session.add(self.club)
        db.session.flush()
        
        # Assign roles via UserClub
        db.session.add(UserClub(
            user_id=self.user_admin.id,
            club_id=self.club.id,
            club_role_id=self.role_admin.id,
            contact_id=self.contact_admin.id
        ))
        db.session.add(UserClub(
            user_id=self.user_user.id,
            club_id=self.club.id,
            club_role_id=self.role_user.id,
            contact_id=self.contact_user.id
        ))
        db.session.commit()

    def test_model_has_permission(self):
        """Test User.has_permission method."""
        # Admin should have both
        self.assertTrue(self.user_admin.has_permission(Permissions.AGENDA_VIEW))
        self.assertTrue(self.user_admin.has_permission(Permissions.AGENDA_EDIT))
        
        # User should only have view
        self.assertTrue(self.user_user.has_permission(Permissions.AGENDA_VIEW))
        self.assertFalse(self.user_user.has_permission(Permissions.AGENDA_EDIT))

    def test_model_has_role(self):
        """Test User.has_role method."""
        self.assertTrue(self.user_admin.has_role("SysAdmin"))
        self.assertFalse(self.user_admin.has_role("User"))
        
        self.assertTrue(self.user_user.has_role("User"))
        self.assertFalse(self.user_user.has_role("SysAdmin"))

    def test_multiple_roles_union(self):
        """Test that a user gets permissions from their assigned role via UserClub."""
        from app.models import UserClub
        # Create a new role with a unique permission
        perm_special = Permission(name="SPECIAL_PERM", description="Special Permission")
        perm_view = Permission.query.filter_by(name=Permissions.AGENDA_VIEW).first()
        role_special = AuthRole(name="Specialist", description="Specialist Role", level=5)
        role_special.permissions.append(perm_special)
        role_special.permissions.append(perm_view)  # Also give view permission
        db.session.add_all([perm_special, role_special])
        db.session.flush()
        
        # Update user's club role to the special role
        user_club = UserClub.query.filter_by(user_id=self.user_user.id).first()
        user_club.club_role_id = role_special.id
        db.session.commit()
        
        # Force reload
        db.session.expire(self.user_user)
        
        # Should now have both view and special permissions from the Specialist role
        self.assertTrue(self.user_user.has_permission(Permissions.AGENDA_VIEW))
        self.assertTrue(self.user_user.has_permission("SPECIAL_PERM"))
        self.assertFalse(self.user_user.has_permission(Permissions.AGENDA_EDIT))

    def test_context_aware_is_authorized(self):
        """Test is_authorized with meeting manager context."""
        from app.auth.utils import is_authorized
        
        # Create a meeting
        meeting = Meeting(Meeting_Number=500, Meeting_Date=date.today(), status='not started', manager_id=self.contact_user.id, club_id=self.club.id)
        db.session.add(meeting)
        db.session.commit()
        
        # Login as user (who is the manager)
        with self.app.test_request_context():
            from flask_login import login_user
            login_user(self.user_user)
            
            # Member normally can't edit agenda
            # But since they are manager, is_authorized(AGENDA_EDIT, meeting=meeting) should be True
            self.assertTrue(is_authorized(Permissions.AGENDA_EDIT, meeting=meeting))
            
            # Non-managed meeting should still be False
            other_meeting = Meeting(Meeting_Number=501, Meeting_Date=date.today(), status='not started', manager_id=self.contact_admin.id, club_id=self.club.id)
            self.assertFalse(is_authorized(Permissions.AGENDA_EDIT, meeting=other_meeting))

    def test_guest_access_fallback(self):
        """Test is_authorized guest fallback logic."""
        from app.auth.utils import is_authorized
        
        with self.app.test_request_context():
            # No user logged in
            # Default Guest permissions are defined in app/auth/utils.py: ROLE_PERMISSIONS['Guest']
            # Let's verify AGENDA_VIEW is granted to guests
            self.assertTrue(is_authorized(Permissions.AGENDA_VIEW))
            
            # AGENDA_EDIT should NOT be granted to guests
            self.assertFalse(is_authorized(Permissions.AGENDA_EDIT))

    def test_decorators(self):
        """Test permission_required and role_required decorators."""
        from app.auth.permissions import permission_required, role_required
        from flask import jsonify

        @self.app.route('/test-permission')
        @permission_required(Permissions.AGENDA_EDIT)
        def test_perm():
            return jsonify(status="ok")

        @self.app.route('/test-role')
        @role_required("SysAdmin")
        def test_role():
            return jsonify(status="ok")

        # 1. Test as User (should fail)
        with self.client:
            login_resp = self.login("user@test.com", "password")
            self.assertIn(b'Redirecting...', login_resp.data)
            
            resp = self.client.get('/test-permission')
            self.assertEqual(resp.status_code, 403, "User should be forbidden from agenda edit")
            
            resp = self.client.get('/test-role')
            self.assertEqual(resp.status_code, 403, "User should be forbidden from admin role")
            
            self.client.get('/logout') # Explicit logout
            
        # 2. Test as Admin (should pass)
        with self.client:
            login_resp = self.login("admin@test.com", "password")
            self.assertIn(b'Redirecting...', login_resp.data)
            
            resp = self.client.get('/test-permission')
            self.assertEqual(resp.status_code, 200, f"Admin should be allowed agenda edit. Got {resp.status_code}")
            
            resp = self.client.get('/test-role')
            self.assertEqual(resp.status_code, 200, "Admin should be allowed admin role")

    def test_performance_caching(self):
        """Verify that get_permissions uses caching to avoid repeated queries."""
        # Clear cache and expire from session to force fresh load
        self.user_admin._permission_cache = None
        db.session.expire_all()
        
        from sqlalchemy import event
        count = [0]
        
        @event.listens_for(db.engine, "before_cursor_execute")
        def count_queries(conn, cursor, statement, parameters, context, executemany):
            # Focus on permission/role permission related tables
            stmt_low = statement.lower()
            if "permission" in stmt_low or "role" in stmt_low:
                count[0] += 1
        
        # First call should trigger queries
        # Re-fetch user to make sure it's fresh in session
        user = db.session.get(User, self.user_admin.id)
        perms1 = user.get_permissions()
        initial_count = count[0]
        self.assertGreater(initial_count, 0, "Initial call should trigger database queries")
        
        # Subsequent calls should NOT trigger more queries
        user.has_permission(Permissions.AGENDA_VIEW)
        user.has_permission(Permissions.AGENDA_EDIT)
        
        self.assertEqual(count[0], initial_count, "Database should not be queried again after first permission check")
        
        # Verify cache clearing works
        user._permission_cache = None
        # Expire to force relationship reload
        db.session.expire(user)
        user.get_permissions()
        self.assertGreater(count[0], initial_count, "Database should be queried again after cache is cleared and object expired")
        
        # Remove listener
        event.remove(db.engine, "before_cursor_execute", count_queries)

    def test_user_multiple_roles_assignment(self):
        """Test assigning multiple roles to a user through UserClub."""
        from app.models import AuthRole, UserClub
        # Use existing roles from setup
        role_admin = AuthRole.query.filter_by(name='SysAdmin').first()
        role_user = AuthRole.query.filter_by(name='User').first()
        
        # Clear existing
        UserClub.query.filter_by(user_id=self.user_user.id).delete()
        
        # Add user with admin role in the club
        db.session.add(UserClub(
            user_id=self.user_user.id,
            club_id=self.club.id,
            club_role_id=role_admin.id,
            contact_id=self.contact_user.id
        ))
        db.session.commit()
        
        # Verify - user should now have SysAdmin role
        db.session.expire(self.user_user)  # Force reload of relationships
        self.assertTrue(self.user_user.has_role('SysAdmin'))
        # Note: User will only have one role now (the highest one assigned via UserClub)
        

    def test_permission_audit_logging(self):
        """Test that permission audits are recorded correctly."""
        from app.models import PermissionAudit
        
        audit = PermissionAudit(
            admin_id=self.user_admin.id,
            action='UPDATE_ROLE_PERMS',
            target_type='ROLE',
            target_id=self.role_admin.id,
            target_name='SysAdmin',
            changes='{"added": [1, 2], "removed": []}'
        )
        db.session.add(audit)
        db.session.commit()
        
        saved_audit = PermissionAudit.query.filter_by(admin_id=self.user_admin.id).first()
        self.assertIsNotNone(saved_audit)
        self.assertEqual(saved_audit.action, 'UPDATE_ROLE_PERMS')
        self.assertEqual(saved_audit.target_name, 'SysAdmin')
        
        # Test to_dict
        d = saved_audit.to_dict()
        self.assertEqual(d['admin_name'], self.user_admin.contact.Name)
        self.assertEqual(d['action'], 'UPDATE_ROLE_PERMS')

    def login(self, email, password):
        return self.client.post('/login', data=dict(
            username=email,
            password=password
        ), follow_redirects=False) # Changed to False to verify redirect manually

if __name__ == '__main__':
    unittest.main()
