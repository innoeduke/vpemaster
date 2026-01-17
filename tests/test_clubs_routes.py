
import pytest
from app.models import Club, User, AuthRole, UserClub
from app.auth.permissions import Permissions
from flask import url_for

@pytest.fixture
def db_session(app):
    with app.app_context():
        from app import db
        yield db.session
        db.session.remove()

@pytest.fixture
def sysadmin_user(app, db_session):
    """Create a SysAdmin user for testing."""
    # Ensure role exists
    role = AuthRole.get_by_name(Permissions.SYSADMIN)
    if not role:
        role = AuthRole(name=Permissions.SYSADMIN)
        db_session.add(role)
        db_session.commit()

    # Ensure club exists
    club = Club.query.filter_by(club_no="000_TEST").first()
    if not club:
         club = Club(club_no="000_TEST", club_name="Default Test Club")
         db_session.add(club)
         db_session.commit()

    # Create user
    user = User.query.filter_by(email='sysadmin_test@example.com').first()
    if not user:
        user = User(username='sysadmin_test', email='sysadmin_test@example.com', password_hash='hash')
        db_session.add(user)
        db_session.commit()
    
    # Ensure contact exists
    contact = Contact.query.filter_by(Email=user.email).first()
    if not contact:
        contact = Contact(Name='SysAdmin Test', Email=user.email, first_name='SysAdmin', last_name='Test')
        db_session.add(contact)
        db_session.commit()
        user.contact_id = contact.id
        db_session.commit()

    # Assign role and club
    if not UserClub.query.filter_by(user_id=user.id, club_id=club.id, club_role_id=role.id).first():
        user_club = UserClub(user_id=user.id, club_id=club.id, club_role_id=role.id, contact_id=contact.id, is_home=True)
        db_session.add(user_club)
        db_session.commit()
    
    # Ensure primary club linkage
    from app.models import ContactClub
    if not ContactClub.query.filter_by(contact_id=contact.id, club_id=club.id).first():
        cc = ContactClub(contact_id=contact.id, club_id=club.id, is_primary=True, membership_type='Member')
        db_session.add(cc)
        db_session.commit()
    
    return user

@pytest.fixture
def regular_user(app, db_session):
    """Create a regular user for testing."""
    user = User.query.filter_by(email='regular_test@example.com').first()
    if not user:
        user = User(username='regular_test', email='regular_test@example.com', password_hash='hash')
        db_session.add(user)
        db_session.commit()
    
    # Ensure contact exists
    contact = Contact.query.filter_by(Email=user.email).first()
    if not contact:
        contact = Contact(Name='Regular Test', Email=user.email, first_name='Regular', last_name='Test')
        db_session.add(contact)
        db_session.commit()
        user.contact_id = contact.id
        db_session.commit()

    # Ensure primary club linkage
    from app.models import ContactClub, Club
    club = Club.query.first()
    if not ContactClub.query.filter_by(contact_id=contact.id, club_id=club.id).first():
        cc = ContactClub(contact_id=contact.id, club_id=club.id, is_primary=True, membership_type='Member')
        db_session.add(cc)
        db_session.commit()

    return user

def test_list_clubs_sysadmin(client, sysadmin_user):
    """Test that SysAdmin can view the clubs list."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(sysadmin_user.id)
        sess['_fresh'] = True

    response = client.get('/clubs')
    assert response.status_code == 200
    assert b'Club Management' in response.data

def test_list_clubs_forbidden(client, regular_user):
    """Test that regular users cannot view the clubs list."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(regular_user.id)
        sess['_fresh'] = True

    response = client.get('/clubs', follow_redirects=True)
    # Should redirect or show error
    # Adjust assertion based on actual behavior (redirect to dashboard likely)
    assert response.status_code == 200
    # Assuming redirect to dashboard or login
    assert b'Club Management' not in response.data

def test_create_club(client, sysadmin_user, db_session):
    """Test creating a new club."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(sysadmin_user.id)
        sess['_fresh'] = True

    # cleanup if exists
    existing = Club.query.filter_by(club_no='9999').first()
    if existing:
        db_session.delete(existing)
        db_session.commit()

    import random
    unique_no = str(random.randint(10000, 99999))
    data = {
        'club_no': unique_no,
        'club_name': 'Test Club ' + unique_no,
        'short_name': 'Test',
        'district': '99',
        'division': 'Z',
        'area': '1'
    }
    response = client.post('/clubs/new', data=data, follow_redirects=True)
    assert response.status_code == 200
    assert b'Club created successfully' in response.data
    
    # Check DB
    club = Club.query.filter_by(club_no=unique_no).first()
    assert club is not None
    assert club.club_name == 'Test Club ' + unique_no

    # Cleanup
    db_session.delete(club)
    db_session.commit()

def test_edit_club(client, sysadmin_user, db_session):
    """Test editing an existing club."""
    import random
    unique_no = str(random.randint(10000, 99999))
    club = Club(club_no=unique_no, club_name='Old Name')
    db_session.add(club)
    db_session.commit()
    
    with client.session_transaction() as sess:
        sess['_user_id'] = str(sysadmin_user.id)
        sess['_fresh'] = True

    data = {
        'club_no': unique_no,
        'club_name': 'New Name'
    }
    response = client.post(f'/clubs/{club.id}/edit', data=data, follow_redirects=True)
    assert response.status_code == 200
    assert b'Club updated successfully' in response.data
    
    updated_club = db_session.get(Club, club.id)
    assert updated_club.club_name == 'New Name'

    # Cleanup
    db_session.delete(updated_club)
    db_session.commit()

def test_delete_club(client, sysadmin_user, db_session):
    """Test deleting a club."""
    import random
    unique_no = str(random.randint(10000, 99999))
    club = Club(club_no=unique_no, club_name='To Delete')
    db_session.add(club)
    db_session.commit()
    
    with client.session_transaction() as sess:
        sess['_user_id'] = str(sysadmin_user.id)
        sess['_fresh'] = True

    response = client.post(f'/clubs/{club.id}/delete', follow_redirects=True)
    assert response.status_code == 200
    assert b'Club deleted successfully' in response.data
    
    deleted_club = db_session.get(Club, club.id)
    assert deleted_club is None
