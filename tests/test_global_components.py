
import pytest
from app import create_app, db
from app.models.club import Club
from app.models.roster import MeetingRole
from app.models.session import SessionType
from app.constants import GLOBAL_CLUB_ID


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test_secret'
    WTF_CSRF_ENABLED = False

@pytest.fixture
def app_context():
    # Pass the TestConfig object directly to create_app
    app = create_app(config_class=TestConfig)
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

def get_or_create_club(id, **kwargs):
    club = db.session.get(Club, id)
    if not club:
        club = Club(id=id, **kwargs)
        db.session.add(club)
    return club

def test_global_roles_visibility(app_context):
    """Test that Club 1 roles are visible to other clubs."""
    
    # 1. Create Clubs
    # Ensure Club 1 exists (simulating System Club)
    system_club = get_or_create_club(GLOBAL_CLUB_ID, club_name="System Club", club_no="000001")
    other_club = Club(club_name="Other Club", club_no="999999")
    db.session.add(other_club)
    db.session.commit()
    
    other_club_id = other_club.id
    
    # 2. Add Global Role
    global_role = MeetingRole(name="GlobalToastmaster", type="standard", 
                              needs_approval=False, has_single_owner=True, 
                              club_id=GLOBAL_CLUB_ID)
    db.session.add(global_role)
    db.session.commit()
    
    # 3. Fetch for Other Club
    fetched_roles = MeetingRole.get_all_for_club(other_club_id)
    role_names = [r.name for r in fetched_roles]
    
    assert "GlobalToastmaster" in role_names
    assert len(fetched_roles) == 1
    assert fetched_roles[0].club_id == GLOBAL_CLUB_ID

def test_local_roles_visibility(app_context):
    """Test that Local roles are visible to the specific club."""
    
    # Setup Clubs
    system_club = get_or_create_club(GLOBAL_CLUB_ID, club_name="System Club", club_no="000001")
    club_x = Club(club_name="Club X", club_no="123456")
    db.session.add(club_x)
    db.session.commit()
    
    # Add Local Role
    local_role = MeetingRole(name="LocalRole", type="club-specific", 
                             needs_approval=False, has_single_owner=True, 
                             club_id=club_x.id)
    db.session.add(local_role)
    db.session.commit()
    
    # Fetch for Club X
    fetched_roles = MeetingRole.get_all_for_club(club_x.id)
    role_names = [r.name for r in fetched_roles]
    
    assert "LocalRole" in role_names
    assert len(fetched_roles) == 1

def test_local_override_global(app_context):
    """Test that a Local role overrides a Global role with the same name."""
    
    # Setup Clubs
    system_club = get_or_create_club(GLOBAL_CLUB_ID, club_name="System Club", club_no="000001")
    club_x = Club(club_name="Club X", club_no="123456")
    db.session.add(club_x)
    db.session.commit()
    
    # Add Global Role
    global_role = MeetingRole(name="Toastmaster", type="standard", 
                              needs_approval=False, has_single_owner=True, 
                              club_id=GLOBAL_CLUB_ID)
    db.session.add(global_role)
    db.session.commit()
    
    # Add Local Override
    # E.g. unique needs_approval setting
    local_role = MeetingRole(name="Toastmaster", type="club-specific", 
                             needs_approval=True, has_single_owner=True, 
                             club_id=club_x.id)
    db.session.add(local_role)
    db.session.commit()
    
    # Fetch for Club X
    fetched_roles = MeetingRole.get_all_for_club(club_x.id)
    
    assert len(fetched_roles) == 1
    fetched_role = fetched_roles[0]
    
    assert fetched_role.name == "Toastmaster"
    assert fetched_role.club_id == club_x.id
    assert fetched_role.needs_approval is True  # Override value
    assert fetched_role.id == local_role.id

def test_cross_club_isolation(app_context):
    """Test that Club Y does not see Club X's local roles."""
    
    # Setup Clubs
    system_club = get_or_create_club(GLOBAL_CLUB_ID, club_name="System Club", club_no="000001")
    club_x = Club(club_name="Club X", club_no="123456")
    club_y = Club(club_name="Club Y", club_no="654321")
    db.session.add(club_x)
    db.session.add(club_y)
    db.session.commit()
    
    # Add Role to X
    role_x = MeetingRole(name="RoleX", type="club-specific", 
                         needs_approval=False, has_single_owner=True, 
                         club_id=club_x.id)
    # Add Global Role
    role_g = MeetingRole(name="RoleGlobal", type="standard", 
                         needs_approval=False, has_single_owner=True, 
                         club_id=GLOBAL_CLUB_ID)
    db.session.add(role_x)
    db.session.add(role_g)
    db.session.commit()
    
    # Fetch for Club Y
    # Should see Global, but NOT RoleX
    roles_y = MeetingRole.get_all_for_club(club_y.id)
    names_y = [r.name for r in roles_y]
    
    assert "RoleGlobal" in names_y
    assert "RoleX" not in names_y

def test_session_type_override(app_context):
    """Test SessionType overrides similarly to Roles."""
    
    system_club = get_or_create_club(GLOBAL_CLUB_ID, club_name="System Club", club_no="000001")
    club_x = Club(club_name="Club X", club_no="123456")
    db.session.add(club_x)
    db.session.commit()
    
    # Global Session Type
    st_global = SessionType(Title="Prepared Speech", Duration_Min=5, 
                            club_id=GLOBAL_CLUB_ID)
    db.session.add(st_global)
    db.session.commit()
    
    # Local Session Type Override
    st_local = SessionType(Title="Prepared Speech", Duration_Min=10, 
                           club_id=club_x.id)
    db.session.add(st_local)
    db.session.commit()
    
    # Verify get_all_for_club
    all_types = SessionType.get_all_for_club(club_x.id)
    assert len(all_types) == 1
    assert all_types[0].Duration_Min == 10
    assert all_types[0].club_id == club_x.id
    
    # Verify get_id_by_title
    found_id = SessionType.get_id_by_title("Prepared Speech", club_x.id)
    assert found_id == st_local.id
    
    # Verify get_ids_for_club
    ids_map = SessionType.get_ids_for_club(club_x.id)
    assert ids_map["Prepared Speech"] == st_local.id
    
