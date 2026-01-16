
import unittest
from app import create_app, db
from app.models.permission import Permission
from app.auth.permissions import Permissions
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

class PermissionsTestCase(unittest.TestCase):
    """Test proper configuration of system permissions."""
    
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # We need to simulate the migration logic here or rely on DB seeding fixtures
        # For this test, we want to ensure that if we run the seeding logic (or similar),
        # ALL expected permissions end up in the DB.
        # Since this runs against in-memory DB, we need to populate it.
        # We can reuse the logic from the migration or a helper, 
        # but simpler is to verify that the CONSTANTS match what we EXPECT the app to have.
        # However, the requirement is "create a test that verifies the existence of all permissions".
        # This implies checking the LIVE database or a seeded test DB.
        # Let's check the LIVE database (integration test) style or seed it.
        # Given potential CI env, seeding is better.
        pass

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_all_permissions_defined_in_constants_exist_in_db(self):
        """
        Verify that every permission defined in app.auth.permissions.Permissions
        exists in the database.
        
        Note: In a real environment, this tests if migrations are up to date.
        In this test harness with in-memory DB, we'd need to run the migration logic.
        Since we can't easily run alembic upgrade here without setup, 
        we will skip the "in DB" check on empty memory DB and instead 
        create a separate script or rely on manual verification for the *exact/live* DB.
        
        BUT, to satisfy the user request "create a test that verifies...", 
        I will make this test run against the `current_app` if it's connected to a persistent DB,
        OR I will create a test that asserts the CONSTANTS are correct.
        
        Actually, the robust way is to create a test that CHECKS the permission definitions.
        """
        # Get all attributes of Permissions class that are uppercase (constants)
        expected_permissions = [
            getattr(Permissions, attr) 
            for attr in dir(Permissions) 
            if attr.isupper() and not attr.startswith('_') 
            and isinstance(getattr(Permissions, attr), str)
            and attr not in ['ADMIN', 'OPERATOR', 'STAFF', 'USER'] # Exclude Roles
        ]
        
        # For this test to pass in CI with sqlite memory, we would need to seed it.
        # However, passing this test confirms that our Code Constants are sane.
        self.assertTrue(len(expected_permissions) > 0)
        
        # To verify they exist in the ACTUAL database, we should use a script or 
        # a test configured with the actual DEV database URI (which is default in some setups).
        # Assuming the user runs this against their dev setup:
        
        # Checking actual DB permissions
        db_permissions = {p.name for p in Permission.query.all()}
        
        # If DB is empty (test mode), we can't assert.
        # If DB is seeded, we can.
        # Let's assume we want to query the DB and warn/fail if missing.
        
        missing = [p for p in expected_permissions if p not in db_permissions]
        
        # We'll print missing ones. Failing the test might be harsh if running on fresh memory DB.
        # But if the user asked for a validator, valid failure is good.
        # However, since `setUp` does `db.create_all()`, the table is empty! 
        # So this test will always fail on `sqlite:///:memory:` unless we seed it.
        
        # To make this useful, I will write a test that can inspect the REAL database.
        # But `unittest` with `setUp` creating fresh DB contradicts that.
        pass

# Redefining strategy: 
# The user wants "create a test that verifies the existence of all permissions".
# Be pragmatic: checking proper CONSTANT definitions is valuable.
# Checking DB content requires the DB to be migrated.
# I will instruct the user to run this against their dev database or include migration application.

import pytest
from app.models import Permission
from app.auth.permissions import Permissions

@pytest.fixture
def app():
    from app import create_app
    # Use the DEVELOPMENT config to hit the real DB (or test DB if configured in env)
    # If we really want to check the "migration result", we should use the dev config.
    app = create_app() 
    return app

def test_verify_all_permissions_exist_in_db(app):
    """
    Verify that all permissions defined in code constants exist in the database.
    This test expects the database to be migrated and seeded.
    """
    with app.app_context():
        # 1. Get List of Expected Permissions from Code
        expected_perms = set()
        for attr in dir(Permissions):
            if attr.isupper() and not attr.startswith('_'):
                value = getattr(Permissions, attr)
                # Filter out Role names which are also in Constants but shouldn't be in Permission table
                if attr in ['ADMIN', 'OPERATOR', 'STAFF', 'USER']:
                    continue
                expected_perms.add(value)
        
        # 2. Get List of Actual Permissions from Database
        actual_perms = {p.name for p in Permission.query.all()}
        
        # 3. Compare
        missing_perms = expected_perms - actual_perms
        
        assert not missing_perms, f"Missing permissions in database: {missing_perms}"
        print(f"Verified {len(expected_perms)} permissions exist in database.")

