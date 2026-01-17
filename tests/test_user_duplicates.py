import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Contact, Club, ContactClub, AuthRole
from app.club_context import set_current_club_id
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SERVER_NAME = 'localhost.localdomain'

@pytest.fixture
def test_app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        # Seed basic roles
        if not AuthRole.query.filter_by(name='User').first():
            db.session.add(AuthRole(name='User', description='User role'))
        if not AuthRole.query.filter_by(name='Staff').first():
            db.session.add(AuthRole(name='Staff', description='Staff role'))
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def test_client(test_app):
    return test_app.test_client()

def test_duplicate_user_in_current_club(test_app, test_client):
    """Scenario 1: Duplicate user in current club should be marked as in_current_club."""
    with test_app.app_context():
        club = Club(club_no='111', club_name='Club A')
        db.session.add(club)
        db.session.commit()
        
        # Create an admin user to perform the check
        admin_contact = Contact(Name='Admin', Email='admin@test.com')
        db.session.add(admin_contact)
        db.session.commit()
        admin_user = User(username='admin', email='admin@test.com', contact_id=admin_contact.id)
        admin_user.set_password('password')
        db.session.add(admin_user)
        db.session.commit()

        # Login
        test_client.post('/login', data={'username': 'admin', 'password': 'password'})
        
        contact = Contact(Name='Duplicate User', Email='dup@test.com')
        contact.first_name = 'Duplicate'
        contact.last_name = 'User'
        db.session.add(contact)
        db.session.commit()
        
        user = User(username='dupuser', email='dup@test.com', contact_id=contact.id)
        user.set_password('password')
        db.session.add(user)
        
        cc = ContactClub(contact_id=contact.id, club_id=club.id, membership_type='Member')
        db.session.add(cc)
        db.session.commit()
        
        with test_client.session_transaction() as sess:
            sess['current_club_id'] = club.id
        
        # Trigger: Check duplicates
        response = test_client.post('/user/check_duplicates', json={
            'username': 'dupuser',
            'full_name': 'Duplicate User',
            'email': 'dup@test.com'
        })
        
        data = response.get_json()
        assert len(data['duplicates']) == 1
        assert data['duplicates'][0]['in_current_club'] is True
        assert data['suggested_username'] == 'dupuser1'

def test_duplicate_user_not_in_current_club(test_app, test_client):
    """Scenario 2: Duplicate user in DIFFERENT club should have in_current_club=False."""
    with test_app.app_context():
        club_a = Club(club_no='222', club_name='Club A')
        club_b = Club(club_no='333', club_name='Club B')
        db.session.add_all([club_a, club_b])
        db.session.commit()

        # Login
        admin_contact = Contact(Name='Admin', Email='admin@test.com')
        db.session.add(admin_contact)
        db.session.commit()
        admin_user = User(username='admin', email='admin@test.com', contact_id=admin_contact.id)
        admin_user.set_password('password')
        db.session.add(admin_user)
        db.session.commit()
        test_client.post('/login', data={'username': 'admin', 'password': 'password'})
        
        contact = Contact(Name='External User', Email='ext@test.com')
        contact.first_name = 'External'
        contact.last_name = 'User'
        db.session.add(contact)
        db.session.commit()
        
        user = User(username='extuser', email='ext@test.com', contact_id=contact.id)
        user.set_password('password')
        db.session.add(user)
        
        cc = ContactClub(contact_id=contact.id, club_id=club_a.id, membership_type='Member')
        db.session.add(cc)
        db.session.commit()
        
        with test_client.session_transaction() as sess:
            sess['current_club_id'] = club_b.id
        
        # Trigger: Check duplicates
        response = test_client.post('/user/check_duplicates', json={
            'username': 'extuser',
            'full_name': 'External User',
            'email': 'ext@test.com'
        })
        
        data = response.get_json()
        assert len(data['duplicates']) == 1
        assert data['duplicates'][0]['in_current_club'] is False

def test_duplicate_contact_guest_in_current_club(test_app, test_client):
    """Scenario 3: Guest in current club should be detectable for conversion."""
    with test_app.app_context():
        club = Club(club_no='444', club_name='Club A')
        db.session.add(club)
        db.session.commit()

        # Login
        admin_contact = Contact(Name='Admin', Email='admin@test.com')
        db.session.add(admin_contact)
        db.session.commit()
        admin_user = User(username='admin', email='admin@test.com', contact_id=admin_contact.id)
        admin_user.set_password('password')
        db.session.add(admin_user)
        db.session.commit()
        test_client.post('/login', data={'username': 'admin', 'password': 'password'})
        
        contact = Contact(Name='Guest User', Email='guest@test.com')
        contact.first_name = 'Guest'
        contact.last_name = 'User'
        db.session.add(contact)
        db.session.commit()
        
        cc = ContactClub(contact_id=contact.id, club_id=club.id, membership_type='Guest')
        db.session.add(cc)
        db.session.commit()
        
        with test_client.session_transaction() as sess:
            sess['current_club_id'] = club.id
        
        response = test_client.post('/user/check_duplicates', json={
            'full_name': 'Guest User',
            'email': 'guest@test.com'
        })
        
        data = response.get_json()
        assert len(data['duplicates']) == 1
        assert data['duplicates'][0]['type'] == 'Contact'
        assert data['duplicates'][0]['in_current_club'] is True

def test_duplicate_contact_guest_in_other_club(test_app, test_client):
    """Scenario 4: Guest in OTHER club should NOT be considered a duplicate."""
    with test_app.app_context():
        club_a = Club(club_no='555', club_name='Club A')
        club_b = Club(club_no='666', club_name='Club B')
        db.session.add_all([club_a, club_b])
        db.session.commit()

        # Login
        admin_contact = Contact(Name='Admin', Email='admin@test.com')
        db.session.add(admin_contact)
        db.session.commit()
        admin_user = User(username='admin', email='admin@test.com', contact_id=admin_contact.id)
        admin_user.set_password('password')
        db.session.add(admin_user)
        db.session.commit()
        test_client.post('/login', data={'username': 'admin', 'password': 'password'})
        
        contact = Contact(Name='Other Club Guest', Email='other@test.com')
        contact.first_name = 'Other'
        contact.last_name = 'Club'
        db.session.add(contact)
        db.session.commit()
        
        cc = ContactClub(contact_id=contact.id, club_id=club_a.id, membership_type='Guest')
        db.session.add(cc)
        db.session.commit()
        
        with test_client.session_transaction() as sess:
            sess['current_club_id'] = club_b.id
        
        response = test_client.post('/user/check_duplicates', json={
            'full_name': 'Other Club Guest',
            'email': 'other@test.com'
        })
        
        data = response.get_json()
        assert len(data['duplicates']) == 0
