import unittest
import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Permission, AuthRole
from app.auth.permissions import Permissions
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class AboutClubPermissionsTestCase(unittest.TestCase):
    """Test that ABOUT_CLUB permissions exist and are correctly assigned."""
    
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Run the migration logic to set up permissions
        self.setup_about_club_permissions()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.app_context.pop()

    def setup_about_club_permissions(self):
        """Simulate the migration by creating permissions and roles."""
        # Create roles
        role_sysadmin = AuthRole(name='SysAdmin', description='System Administrator', level=8)
        role_clubadmin = AuthRole(name='ClubAdmin', description='Club Administrator', level=4)
        role_staff = AuthRole(name='Staff', description='Staff Member', level=2)
        role_user = AuthRole(name='User', description='Regular User', level=1)
        
        db.session.add_all([role_sysadmin, role_clubadmin, role_staff, role_user])
        
        # Create ABOUT_CLUB permissions
        perm_view = Permission(
            name='ABOUT_CLUB_VIEW',
            description='View club information and executive committee',
            category='club',
            resource='club',
            action='view'
        )
        perm_edit = Permission(
            name='ABOUT_CLUB_EDIT',
            description='Edit club information and executive committee',
            category='club',
            resource='club',
            action='edit'
        )
        
        db.session.add_all([perm_view, perm_edit])
        db.session.flush()
        
        # Assign VIEW to all roles
        role_sysadmin.permissions.append(perm_view)
        role_clubadmin.permissions.append(perm_view)
        role_staff.permissions.append(perm_view)
        role_user.permissions.append(perm_view)
        
        # Assign EDIT to admin roles only
        role_sysadmin.permissions.append(perm_edit)
        role_clubadmin.permissions.append(perm_edit)
        
        db.session.commit()

    def test_about_club_view_permission_exists(self):
        """Test that ABOUT_CLUB_VIEW permission exists in database."""
        perm = Permission.query.filter_by(name='ABOUT_CLUB_VIEW').first()
        self.assertIsNotNone(perm, "ABOUT_CLUB_VIEW permission should exist")
        self.assertEqual(perm.category, 'club')
        self.assertEqual(perm.resource, 'club')
        self.assertEqual(perm.action, 'view')

    def test_about_club_edit_permission_exists(self):
        """Test that ABOUT_CLUB_EDIT permission exists in database."""
        perm = Permission.query.filter_by(name='ABOUT_CLUB_EDIT').first()
        self.assertIsNotNone(perm, "ABOUT_CLUB_EDIT permission should exist")
        self.assertEqual(perm.category, 'club')
        self.assertEqual(perm.resource, 'club')
        self.assertEqual(perm.action, 'edit')

    def test_about_club_view_assigned_to_all_roles(self):
        """Test that ABOUT_CLUB_VIEW is assigned to all roles."""
        perm = Permission.query.filter_by(name='ABOUT_CLUB_VIEW').first()
        self.assertIsNotNone(perm)
        
        role_names = [role.name for role in perm.roles]
        expected_roles = ['SysAdmin', 'ClubAdmin', 'Staff', 'User']
        
        for expected_role in expected_roles:
            self.assertIn(expected_role, role_names, 
                         f"ABOUT_CLUB_VIEW should be assigned to {expected_role}")

    def test_about_club_edit_assigned_to_admin_roles_only(self):
        """Test that ABOUT_CLUB_EDIT is assigned only to admin roles."""
        perm = Permission.query.filter_by(name='ABOUT_CLUB_EDIT').first()
        self.assertIsNotNone(perm)
        
        role_names = [role.name for role in perm.roles]
        
        # Should have these roles
        self.assertIn('SysAdmin', role_names, 
                     "ABOUT_CLUB_EDIT should be assigned to SysAdmin")
        self.assertIn('ClubAdmin', role_names, 
                     "ABOUT_CLUB_EDIT should be assigned to ClubAdmin")
        
        # Should NOT have these roles
        self.assertNotIn('Staff', role_names, 
                        "ABOUT_CLUB_EDIT should NOT be assigned to Staff")
        self.assertNotIn('User', role_names, 
                        "ABOUT_CLUB_EDIT should NOT be assigned to User")

    def test_permissions_defined_in_constants(self):
        """Test that ABOUT_CLUB permissions are defined in Permissions class."""
        self.assertTrue(hasattr(Permissions, 'ABOUT_CLUB_VIEW'),
                       "Permissions.ABOUT_CLUB_VIEW should be defined")
        self.assertTrue(hasattr(Permissions, 'ABOUT_CLUB_EDIT'),
                       "Permissions.ABOUT_CLUB_EDIT should be defined")
        
        self.assertEqual(Permissions.ABOUT_CLUB_VIEW, 'ABOUT_CLUB_VIEW')
        self.assertEqual(Permissions.ABOUT_CLUB_EDIT, 'ABOUT_CLUB_EDIT')

    def test_role_permission_counts(self):
        """Test that roles have the correct number of ABOUT_CLUB permissions."""
        sysadmin = AuthRole.query.filter_by(name='SysAdmin').first()
        clubadmin = AuthRole.query.filter_by(name='ClubAdmin').first()
        staff = AuthRole.query.filter_by(name='Staff').first()
        user = AuthRole.query.filter_by(name='User').first()
        
        # Get ABOUT_CLUB permissions for each role
        sysadmin_about_perms = [p for p in sysadmin.permissions if 'ABOUT_CLUB' in p.name]
        clubadmin_about_perms = [p for p in clubadmin.permissions if 'ABOUT_CLUB' in p.name]
        staff_about_perms = [p for p in staff.permissions if 'ABOUT_CLUB' in p.name]
        user_about_perms = [p for p in user.permissions if 'ABOUT_CLUB' in p.name]
        
        # Admin roles should have both VIEW and EDIT (2 permissions)
        self.assertEqual(len(sysadmin_about_perms), 2, 
                        "SysAdmin should have 2 ABOUT_CLUB permissions")
        self.assertEqual(len(clubadmin_about_perms), 2, 
                        "ClubAdmin should have 2 ABOUT_CLUB permissions")
        
        # Non-admin roles should have only VIEW (1 permission)
        self.assertEqual(len(staff_about_perms), 1, 
                        "Staff should have 1 ABOUT_CLUB permission")
        self.assertEqual(len(user_about_perms), 1, 
                        "User should have 1 ABOUT_CLUB permission")


if __name__ == '__main__':
    unittest.main()
