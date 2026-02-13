"""
Pytest configuration and fixtures.
"""
import sys
import os
import pytest

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))


@pytest.fixture(scope='session')
def app():
    """Create application for testing."""
    from app import create_app
    from config import Config
    
    # Use in-memory SQLite for tests by default to ensure clean state and speed
    class TestConfig(Config):
        TESTING = True
        import tempfile
        db_fd, db_path = tempfile.mkstemp()
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{db_path}'
        WTF_CSRF_ENABLED = False
        SERVER_NAME = 'localhost.localdomain'
        PRESERVE_CONTEXT_ON_EXCEPTION = False

    app = create_app(TestConfig)
    
    # Initialize database
    with app.app_context():
        from app import db
        db.session.configure(expire_on_commit=False)
        db.create_all()
        
    return app

@pytest.fixture(scope='session', autouse=True)
def cleanup_test_artifacts():
    """Cleanup temporary files after the test session."""
    import glob
    yield
    # Cleanup excel files created during tests
    pattern = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'test_meeting_*_export.xlsx'))
    for f in glob.glob(pattern):
        try:
            os.remove(f)
        except OSError:
            pass


@pytest.fixture(scope='function', autouse=True)
def clean_db(app):
    """Clean database between tests."""
    with app.app_context():
        from app import db
        # Drop all tables and recreate them to ensure a clean slate
        db.drop_all()
        db.create_all()
    yield

@pytest.fixture(scope='function')
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture(scope='function')
def default_club(app):
    """Get or create a default club for testing."""
    from app.models import db, Club
    
    with app.app_context():
        club = Club.query.first()
        if not club:
            # Create a test club if none exists
            club = Club(
                club_no='000000',
                club_name='Test Club',
                district='Test District',
                division='Test Division',
                area='Test Area'
            )
            db.session.add(club)
            db.session.commit()
            db.session.refresh(club)
        
        db.session.refresh(club)
        
        return club


@pytest.fixture(scope='function')
def default_excomm(app, default_club):
    """Get or create a default ExComm for testing."""
    from app.models import db, ExComm
    
    with app.app_context():
        excomm = ExComm.query.first()
        if not excomm:
            # Create a test ExComm if none exists
            excomm = ExComm(
                club_id=default_club.id,
                excomm_term='26H1'
            )
            db.session.add(excomm)
            db.session.commit()
            db.session.refresh(excomm)
        
        return excomm


@pytest.fixture(scope='function')
def default_contact(app):
    """Get or create a default Contact for testing."""
    from app.models import db, Contact
    
    with app.app_context():
        # Try to find an existing contact or create one
        contact = Contact.query.filter_by(Name='Test User').first()
        if not contact:
            contact = Contact(
                Name='Test User',
                Type='Member',
                Email='test@example.com'
            )
            db.session.add(contact)
            db.session.commit()
            db.session.refresh(contact)
        
        return contact


@pytest.fixture(scope='function')
def user1(app):
    """Create a user with ID 1."""
    from app.models import db, User
    with app.app_context():
        user = User.query.get(1)
        if not user:
            user = User(id=1, username='user1', email='user1@example.com')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()
            db.session.refresh(user)
        return user
@pytest.fixture(scope='function')
def seeded_permissions(app):
    """Seed permissions into the database."""
    from app.models import db, Permission
    from app.auth.permissions import Permissions
    
    with app.app_context():
        # Get all constants from Permissions class
        perms = []
        for attr in dir(Permissions):
            if attr.isupper() and not attr.startswith('_'):
                name = getattr(Permissions, attr)
                if attr in ['SYSADMIN', 'CLUBADMIN', 'STAFF', 'USER']:
                    continue
                if not Permission.query.filter_by(name=name).first():
                    perms.append(Permission(name=name, category='test'))
        
        if perms:
            db.session.add_all(perms)
            db.session.commit()
    yield

@pytest.fixture(scope='function')
def staff_user(app, default_club, default_contact, seeded_permissions):
    """Create a staff user with necessary permissions."""
    from app.models import db, User, AuthRole, UserClub
    from app.auth.permissions import Permissions
    with app.app_context():
        user = User.query.filter_by(username='staff').first()
        if not user:
            user = User(username='staff', email='staff@example.com', status='active')
            user.set_password('password')
            db.session.add(user)
            db.session.flush()
            
            role = AuthRole.query.filter_by(name='Staff').first()
            if not role:
                role = AuthRole(name='Staff', level=2)
                db.session.add(role)
                db.session.flush()
            
            # Ensure staff role has some basic permissions if they are seeded
            from app.models import Permission
            roster_view_perm = Permission.query.filter_by(name=Permissions.ROSTER_VIEW).first()
            if roster_view_perm and roster_view_perm not in role.permissions:
                role.permissions.append(roster_view_perm)
            
            user.roles.append(role)
            
            uc = UserClub(user_id=user.id, club_id=default_club.id, contact_id=default_contact.id, club_role_level=role.level)
            db.session.add(uc)
            db.session.commit()
            db.session.refresh(user)
        return user

@pytest.fixture(scope='function')
def default_contact_club(app, default_contact, default_club):
    """Get or create a default ContactClub association for testing."""
    from app.models import db, ContactClub
    
    with app.app_context():
        cc = ContactClub.query.filter_by(
            contact_id=default_contact.id,
            club_id=default_club.id
        ).first()
        
        if not cc:
            cc = ContactClub(
                contact_id=default_contact.id,
                club_id=default_club.id
            )
            db.session.add(cc)
            db.session.commit()
            db.session.refresh(cc)
        
        return cc

class AuthActions:
    def __init__(self, client):
        self._client = client

    def login(self, username='staff', password='password', club_id=1):
        return self._client.post(
            '/login',
            data={'username': username, 'password': password, 'club_names': club_id},
            follow_redirects=True
        )

    def logout(self):
        return self._client.get('/logout', follow_redirects=True)

@pytest.fixture
def auth(client):
    return AuthActions(client)

@pytest.fixture
def captured_templates(app):
    recorded = []

    def record(sender, template, context, **extra):
        recorded.append(template)

    from flask import template_rendered
    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)
