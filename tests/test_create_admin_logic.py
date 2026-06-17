import unittest
from app import create_app, db
from app.models import User, AuthRole, Club, UserClub
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class CreateAdminLogicTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.runner = self.app.test_cli_runner()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Seed Role
        self.role_admin = AuthRole(name="SysAdmin", description="Admin Role", level=10)
        db.session.add(self.role_admin)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_create_admin_with_existing_club(self):
        """Test creating admin when a club already exists."""
        # Create a club
        club = Club(club_no='111111', club_name='Test Club', district='99')
        db.session.add(club)
        db.session.commit()
        
        # Run command
        result = self.runner.invoke(args=['create-admin', '--username', 'sysadmin', '--email', 'sysadmin@test.com', '--password', 'password', '--password', 'password', '--club-no', '111111'])
        
        # Check output
        print(f"COMMAND OUTPUT:\n{result.output}")
            
        self.assertEqual(result.exit_code, 0)
        
        # Check User
        user = User.query.filter_by(username='sysadmin').first()
        self.assertIsNotNone(user)
        self.assertTrue(user.is_sysadmin, "User should satisfy is_sysadmin check")
        
        # Check UserClub
        uc = UserClub.query.filter_by(user_id=user.id, club_id=club.id).first()
        self.assertIsNotNone(uc)
        self.assertEqual(uc.club_role_level, self.role_admin.level, "UserClub role level should match SysAdmin level")

    def test_create_admin_creates_gossip_club(self):
        """Test creating admin creates the super club if none exists.

        The sysadmin account is restricted to the super club (id=1,
        club_no='000001'). When no clubs exist and the operator runs
        ``create-admin`` for the sysadmin account, the CLI seeds the
        super club rather than a generic 'Gossip' fallback.
        """
        from app.constants import GLOBAL_CLUB_ID
        # Ensure no clubs
        Club.query.delete()
        db.session.commit()

        # Run command without specifying club
        result = self.runner.invoke(args=['create-admin', '--username', 'sysadmin', '--email', 'admin2@test.com', '--password', 'password', '--password', 'password'])

        if result.exit_code != 0:
            print(result.output)

        self.assertEqual(result.exit_code, 0)

        # The super club (id=GLOBAL_CLUB_ID) must be created when no club exists.
        club = db.session.get(Club, GLOBAL_CLUB_ID)
        self.assertIsNotNone(club, "Super club should be created for sysadmin")
        self.assertEqual(club.club_no, '000001')

        # Check User linked to the super club
        user = User.query.filter_by(username='sysadmin').first()
        self.assertIsNotNone(user)
        self.assertTrue(user.is_sysadmin)

        uc = UserClub.query.filter_by(user_id=user.id, club_id=club.id).first()
        self.assertIsNotNone(uc)
        self.assertEqual(uc.club_role_level, self.role_admin.level)

if __name__ == '__main__':
    unittest.main()
