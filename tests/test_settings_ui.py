
import pytest
from app import create_app, db
from app.models import Club, User, SessionType, MeetingRole, UserClub
from app.constants import GLOBAL_CLUB_ID
from types import SimpleNamespace
from bs4 import BeautifulSoup

class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test_secret'
    WTF_CSRF_ENABLED = False

@pytest.fixture
def app_context():
    app = create_app(config_class=TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app_context):
    return app_context.test_client()

def login_user(client, user):
    with client.session_transaction() as sess:
        sess['user_id'] = user.id
        sess['_fresh'] = True

def get_or_create_club(id, **kwargs):
    club = db.session.get(Club, id)
    if not club:
        club = Club(id=id, **kwargs)
        db.session.add(club)
        db.session.commit()
    return club

def test_settings_page_separation(client, app_context):
    """
    Verify that non-Global (Normal) clubs see two tables:
    1. Global items (Read-Only)
    2. Local items (Editable)
    """
    # Setup Data
    global_club = get_or_create_club(GLOBAL_CLUB_ID, club_name="Technical Support", club_no="000001")
    local_club = get_or_create_club(999, club_name="Shanghai Leadership Toastmasters", club_no="00868941")

    # Global Role
    r_global = MeetingRole(name="Global Role", club_id=GLOBAL_CLUB_ID, type='standard', needs_approval=False, has_single_owner=False)
    db.session.add(r_global)
    
    # Local Role
    r_local = MeetingRole(name="Local Role", club_id=999, type='club-specific', needs_approval=False, has_single_owner=False)
    db.session.add(r_local)
    
    # Global Session Type
    st_global = SessionType(Title="Global Session", club_id=GLOBAL_CLUB_ID)
    db.session.add(st_global)
    
    # Local Session Type
    st_local = SessionType(Title="Local Session", club_id=999)
    db.session.add(st_local)
    
    db.session.commit()

    # User setup
    user = User(username='testuser', email='test@test.com', password_hash='hashed_password')
    db.session.add(user)
    db.session.commit()

    # Mock login and authorization
    # We need to mock permissions and club context
    # Since we can't easily mock decorators in integration tests without patching, 
    # we rely on the app's session handling.
    # Note: 'authorized_club_required' decorator checks 'club_id' in session or user preferences.
    
    # Mock authentication and session
    with client.session_transaction() as sess:
        sess['user_id'] = user.id
        sess['_user_id'] = str(user.id) # Flask-Login uses this
        sess['club_id'] = 999 
    
    # We also need to mock "is_authorized" which checks permissions.
    # Instead of complex patching, let's assume `authorized_club_required` sets context 
    # and we might access the route. But `settings` route checks `SETTINGS_VIEW_ALL`.
    # Let's assign permissions to the user via DB.
    from app.models import AuthRole, UserClub
    # Create Admin Role
    role_admin = AuthRole(name="ClubAdmin", level=100) # Assuming 100 is high enough
    db.session.add(role_admin)
    db.session.commit()
    
    # Assign logic is complex (UserClub linkage), let's just patch `is_authorized` for simplicity
    # with app_context.container.permissions.SETTINGS_VIEW_ALL.patch(True):
    #     pass

    # Correct approach: Assign UserClub with a role that has permission.
    # Assuming 'ClubAdmin' has all permissions by default or via checks.
    uc = UserClub(user_id=user.id, club_id=999, club_role_level=100)
    db.session.add(uc)
    db.session.commit()
    
    # We need to ensure 'is_authorized' returns True. 
    # The current auth implementation checks 'current_user.can(...)'.
    # We might need to mock 'current_user'.
    
    # SIMPLIFICATION:
    # Just render the template directly? No, templates need context.
    # Let's perform a Request.
    
    # PATCH: app.auth.utils.is_authorized
    from unittest.mock import patch
    with patch('app.settings_routes.is_authorized', return_value=True):
        with patch('app.settings_routes.authorized_club_required', lambda f: f):
            with patch('app.settings_routes.login_required', lambda f: f):
                # We need to fake `current_user` inside the route?
                # The route uses `get_current_club_id()` which reads session.
                # It uses `User.query...` which needs DB.
                
                response = client.get('/settings')
                assert response.status_code == 200
                html = response.data.decode('utf-8')
                soup = BeautifulSoup(html, 'html.parser')
                
                # Check for Global Session Types Header
                assert "Global Session Types (Standard)" in html
                assert "Global Meeting Roles (Standard)" in html
                
                # Check for Club Specific Header
                assert "Club Specific Session Types" in html
                assert "Club Specific Meeting Roles" in html
                
                # Verify Content Separation
                # "Global Role" should be in the read-only table (id="global-roles-table")
                global_table = soup.find('table', id='global-roles-table')
                assert "Global Role" in str(global_table)
                assert "Local Role" not in str(global_table)
                
                # "Local Role" should be in the editable table (id="roles-table")
                local_table = soup.find('table', id='roles-table')
                assert "Local Role" in str(local_table)
                assert "Global Role" not in str(local_table)
                
                # Check Actions Column absence in Global
                headers = [th.text for th in global_table.find_all('th')]
                assert "Actions" not in headers

def test_settings_page_global_admin(client, app_context):
    """
    Verify that Club 1 (Global) Admin sees merged/single editable view.
    """
    # Setup Data
    global_club = get_or_create_club(GLOBAL_CLUB_ID, club_name="Technical Support", club_no="000001")
    
    r_global = MeetingRole(name="Global Role", club_id=GLOBAL_CLUB_ID, type='standard', needs_approval=False, has_single_owner=False)
    db.session.add(r_global)
    db.session.commit()
    
    user = User(username='admin1', email='admin@vpemaster.com', password_hash='hashed_password')
    db.session.add(user)
    db.session.commit()
    
    uc = UserClub(user_id=user.id, club_id=GLOBAL_CLUB_ID, club_role_level=100)
    db.session.add(uc)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['user_id'] = user.id
        sess['_user_id'] = str(user.id)
        sess['club_id'] = GLOBAL_CLUB_ID
        
    from unittest.mock import patch
    with patch('app.settings_routes.is_authorized', return_value=True):
        response = client.get('/settings')
        assert response.status_code == 200
        html = response.data.decode('utf-8')
        
        # Should NOT see "Global ... (Standard)" headers
        assert "Global Session Types (Standard)" not in html
        assert "Global Meeting Roles (Standard)" not in html
        
        # Should see "Global Repository" header
        assert "Meeting Roles (Global Repository)" in html
        
        # "Global Role" should be in the editable table
        assert "Global Role" in html
