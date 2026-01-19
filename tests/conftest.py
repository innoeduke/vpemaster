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
        SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL', 'sqlite:///:memory:')
        WTF_CSRF_ENABLED = False
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
