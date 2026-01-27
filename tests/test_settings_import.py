
import pytest
import io
from app import create_app, db
from app.models import Club, User, MeetingRole, UserClub
from app.constants import GLOBAL_CLUB_ID

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

def get_or_create_club(id, **kwargs):
    club = db.session.get(Club, id)
    if not club:
        club = Club(id=id, **kwargs)
        db.session.add(club)
        db.session.commit()
    return club

def test_import_roles_logic(client, app_context):
    # Setup Global Club and Role
    global_club = get_or_create_club(GLOBAL_CLUB_ID, club_name="Technical Support", club_no="000001")
    
    # Existing Global Role
    r_global = MeetingRole(name="GlobalToastmaster", club_id=GLOBAL_CLUB_ID, type='standard', 
                           needs_approval=False, has_single_owner=False)
    db.session.add(r_global)
    db.session.commit()
    
    # Setup Local Club
    local_club = get_or_create_club(999, club_name="Test Club", club_no="999")
    
    # Setup User and Login
    user = User(username='testuser', email='test@test.com', password_hash='hash')
    db.session.add(user)
    db.session.commit()
    
    # Assign standard role
    uc = UserClub(user_id=user.id, club_id=999, club_role_level=100)
    db.session.add(uc)
    db.session.commit()

    with client.session_transaction() as sess:
        sess['user_id'] = user.id
        sess['_user_id'] = str(user.id)
        sess['current_club_id'] = 999 

    # Prepare CSV content
    # 1. GlobalToastmaster (Standard) -> Should be skipped (Duplicate of Global)
    # 2. UniqueRole (Standard) -> Should be imported as 'club-specific'
    # 3. LocalRole (Custom) -> Should be imported as 'club-specific'
    csv_content = """name,type,icon,award_category
GlobalToastmaster,standard,fa-user,speaker
UniqueRole,standard,fa-star,speaker
LocalRole,custom,fa-leaf,role-taker
"""
    data = {
        'file': (io.BytesIO(csv_content.encode('utf-8')), 'roles.csv')
    }

    # PATCH permissions
    from unittest.mock import patch
    with patch('app.settings_routes.is_authorized', return_value=True):
        response = client.post('/settings/roles/import', data=data, content_type='multipart/form-data', follow_redirects=True)
        assert response.status_code == 200
        
        # Verify Results
        roles = MeetingRole.query.filter_by(club_id=999).all()
        role_map = {r.name: r for r in roles}
        
        # 1. GlobalToastmaster should NOT be in local roles
        assert "GlobalToastmaster" not in role_map, "Duplicate standard role should be skipped"
        
        # 2. UniqueRole should be imported, BUT type forced to 'club-specific'
        assert "UniqueRole" in role_map
        assert role_map["UniqueRole"].type == 'club-specific', "Imported role should be forced to club-specific"
        
        # 3. LocalRole should be imported as 'club-specific'
        assert "LocalRole" in role_map
        assert role_map["LocalRole"].type == 'club-specific'

