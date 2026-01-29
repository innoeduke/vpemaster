
import pytest
from app.models import Club, User, AuthRole, UserClub, Contact
from app.auth.permissions import Permissions
from flask import url_for



@pytest.fixture
def sysadmin_user(app, default_club):
    """Create a SysAdmin user for testing."""
    from app.models import db, User, AuthRole, UserClub, Contact, ContactClub
    with app.app_context():
        # Ensure role exists
        role = AuthRole.get_by_name(Permissions.SYSADMIN)
        if not role:
            role = AuthRole(name=Permissions.SYSADMIN, level=100)
            db.session.add(role)
            db.session.commit()
            db.session.refresh(role)
        
        # Ensure level is set if already existed
        if role.level is None:
            role.level = 100
            db.session.commit()

        # Create user
        user = User.query.filter_by(email='sysadmin_test@example.com').first()
        if not user:
            user = User(username='sysadmin_test', email='sysadmin_test@example.com', password_hash='hash')
            db.session.add(user)
            db.session.commit()
            db.session.refresh(user)
        
        # Ensure contact exists
        contact = Contact.query.filter_by(Email=user.email).first()
        if not contact:
            contact = Contact(Name='SysAdmin Test', Email=user.email, first_name='SysAdmin', last_name='Test')
            db.session.add(contact)
            db.session.commit()
            db.session.refresh(contact)

        # Assign role and club
        if not UserClub.query.filter_by(user_id=user.id, club_id=default_club.id).first():
            user_club = UserClub(user_id=user.id, club_id=default_club.id, club_role_level=role.level, contact_id=contact.id, is_home=True)
            db.session.add(user_club)
            db.session.commit()
        
        # Ensure primary club linkage
        if not ContactClub.query.filter_by(contact_id=contact.id, club_id=default_club.id).first():
            cc = ContactClub(contact_id=contact.id, club_id=default_club.id)
            db.session.add(cc)
            db.session.commit()
        
        return user

@pytest.fixture
def regular_user(app, default_club):
    """Create a regular user for testing."""
    from app.models import db, User, Contact, ContactClub
    with app.app_context():
        user = User.query.filter_by(email='regular_test@example.com').first()
        if not user:
            user = User(username='regular_test', email='regular_test@example.com', password_hash='hash')
            db.session.add(user)
            db.session.commit()
            db.session.refresh(user)
        
        # Ensure contact exists
        contact = Contact.query.filter_by(Email=user.email).first()
        if not contact:
            contact = Contact(Name='Regular Test', Email=user.email, first_name='Regular', last_name='Test')
            db.session.add(contact)
            db.session.commit()
            db.session.refresh(contact)

        # Ensure primary club linkage
        if not ContactClub.query.filter_by(contact_id=contact.id, club_id=default_club.id).first():
            cc = ContactClub(contact_id=contact.id, club_id=default_club.id)
            db.session.add(cc)
            db.session.commit()

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
    assert response.status_code in [200, 403]
    # Assuming redirect to dashboard or login
    if response.status_code == 200:
        assert b'Club Management' not in response.data

def test_create_club(client, sysadmin_user, app):
    """Test creating a new club."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(sysadmin_user.id)
        sess['_fresh'] = True

    from app.models import db
    with app.app_context():
        # cleanup if exists
        existing = Club.query.filter_by(club_no='9999').first()
        if existing:
            db.session.delete(existing)
            db.session.commit()

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
    
    # Check DB
    with app.app_context():
        club = Club.query.filter_by(club_no=unique_no).first()
        assert club is not None
        assert club.club_name == 'Test Club ' + unique_no

        # Cleanup
        db.session.delete(club)
        db.session.commit()

def test_edit_club(client, sysadmin_user, app):
    """Test editing an existing club."""
    from app.models import db
    import random
    unique_no = str(random.randint(10000, 99999))
    with app.app_context():
        club = Club(club_no=unique_no, club_name='Old Name')
        db.session.add(club)
        db.session.commit()
        club_id = club.id
    
    with client.session_transaction() as sess:
        sess['_user_id'] = str(sysadmin_user.id)
        sess['_fresh'] = True

    data = {
        'club_no': unique_no,
        'club_name': 'New Name'
    }
    response = client.post(f'/clubs/{club_id}/edit', data=data, follow_redirects=True)
    assert response.status_code == 200
    
    with app.app_context():
        updated_club = Club.query.get(club_id)
        assert updated_club.club_name == 'New Name'

        # Cleanup
        db.session.delete(updated_club)
        db.session.commit()

def test_delete_club(client, sysadmin_user, app):
    """Test deleting a club."""
    from app.models import db
    import random
    unique_no = str(random.randint(10000, 99999))
    with app.app_context():
        club = Club(club_no=unique_no, club_name='To Delete')
        db.session.add(club)
        db.session.commit()
        club_id = club.id
    
    with client.session_transaction() as sess:
        sess['_user_id'] = str(sysadmin_user.id)
        sess['_fresh'] = True

    response = client.post(f'/clubs/{club_id}/delete', follow_redirects=True)
    assert response.status_code == 200
    assert b'Club, its meetings, and its specific contacts deleted successfully.' in response.data
    
    with app.app_context():
        deleted_club = Club.query.get(club_id)
        assert deleted_club is None
