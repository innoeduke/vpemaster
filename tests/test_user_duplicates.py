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
        if not AuthRole.query.filter_by(name='Member').first():
            db.session.add(AuthRole(name='Member', description='Member role', level=1))
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
        admin_user = User(username='sysadmin', email='admin@test.com')
        admin_user.set_password('password')
        db.session.add(admin_user)
        db.session.commit()

        from app.models import UserClub
        db.session.add(UserClub(user_id=admin_user.id, club_id=club.id, contact_id=admin_contact.id))
        db.session.commit()

        # Login
        test_client.post('/login', data={'username': 'sysadmin', 'password': 'password'})
        
        contact = Contact(Name='Duplicate User', Email='dup@test.com')
        contact.first_name = 'Duplicate'
        contact.last_name = 'User'
        db.session.add(contact)
        db.session.commit()
        
        user = User(username='dupuser', email='dup@test.com')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        
        from app.models import UserClub
        db.session.add(UserClub(user_id=user.id, club_id=club.id, contact_id=contact.id))
        
        cc = ContactClub(contact_id=contact.id, club_id=club.id)
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
        admin_user = User(username='sysadmin', email='admin@test.com')
        admin_user.set_password('password')
        db.session.add(admin_user)
        db.session.commit()

        from app.models import UserClub
        db.session.add(UserClub(user_id=admin_user.id, club_id=club_a.id, contact_id=admin_contact.id))
        db.session.commit()
        test_client.post('/login', data={'username': 'sysadmin', 'password': 'password'})
        
        contact = Contact(Name='External User', Email='ext@test.com')
        contact.first_name = 'External'
        contact.last_name = 'User'
        db.session.add(contact)
        db.session.commit()
        
        user = User(username='extuser', email='ext@test.com')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        
        from app.models import UserClub
        db.session.add(UserClub(user_id=user.id, club_id=club_a.id, contact_id=contact.id))
        
        cc = ContactClub(contact_id=contact.id, club_id=club_a.id)
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
        admin_user = User(username='sysadmin', email='admin@test.com')
        admin_user.set_password('password')
        db.session.add(admin_user)
        db.session.commit()
        
        from app.models import UserClub
        db.session.add(UserClub(user_id=admin_user.id, club_id=club.id, contact_id=admin_contact.id))
        db.session.commit()
        test_client.post('/login', data={'username': 'sysadmin', 'password': 'password'})
        
        contact = Contact(Name='Guest User', Email='guest@test.com')
        contact.first_name = 'Guest'
        contact.last_name = 'User'
        db.session.add(contact)
        db.session.commit()
        
        cc = ContactClub(contact_id=contact.id, club_id=club.id)
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
        admin_user = User(username='sysadmin', email='admin@test.com')
        admin_user.set_password('password')
        db.session.add(admin_user)
        db.session.commit()

        from app.models import UserClub
        db.session.add(UserClub(user_id=admin_user.id, club_id=club_a.id, contact_id=admin_contact.id))
        db.session.commit()
        test_client.post('/login', data={'username': 'sysadmin', 'password': 'password'})
        
        contact = Contact(Name='Other Club Guest', Email='other@test.com')
        contact.first_name = 'Other'
        contact.last_name = 'Club'
        db.session.add(contact)
        db.session.commit()
        
        cc = ContactClub(contact_id=contact.id, club_id=club_a.id)
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


def test_sysadmin_view_all_users_in_tech_support(test_app, test_client):
    """SysAdmin in Technical Support club (GLOBAL_CLUB_ID=1) context can view all users, even if they don't belong to the club."""
    with test_app.app_context():
        # Setup Technical Support club (ID 1)
        tech_club = Club(id=1, club_no='000001', club_name='Technical Support')
        # Setup another club (ID 2)
        other_club = Club(id=2, club_no='008689', club_name='Other Club')
        db.session.add_all([tech_club, other_club])
        db.session.commit()

        # Create SysAdmin user
        admin = User(username='sysadmin', email='admin@test.com')
        admin.set_password('password')
        db.session.add(admin)
        db.session.commit()

        # Link sysadmin to Technical Support
        from app.models import UserClub
        db.session.add(UserClub(user_id=admin.id, club_id=tech_club.id))
        db.session.commit()

        # Create another user that ONLY belongs to Other Club
        other_contact = Contact(Name='External Member', Email='external@test.com')
        other_contact.first_name = 'External'
        other_contact.last_name = 'Member'
        db.session.add(other_contact)
        db.session.commit()

        other_user = User(username='external_user', email='external@test.com')
        other_user.set_password('password')
        db.session.add(other_user)
        db.session.commit()

        db.session.add(UserClub(user_id=other_user.id, club_id=other_club.id, contact_id=other_contact.id))
        db.session.commit()

    with test_client:
        # Log in as sysadmin
        test_client.post('/login', data={'username': 'sysadmin', 'password': 'password', 'club_names': 1})
        
        # Verify active club is Technical Support (1)
        with test_client.session_transaction() as sess:
            assert sess.get('current_club_id') == 1

        # Request user management list
        response = test_client.get('/api/settings/users')
        assert response.status_code == 200
        
        data = response.get_json()
        assert data['success'] is True
        
        # Verify both users are returned (sysadmin and external_user)
        usernames = [u['username'] for u in data['users']]
        assert 'sysadmin' in usernames
        assert 'external_user' in usernames

        # Verify fallback contact details are populated correctly for external_user
        ext_user_data = next(u for u in data['users'] if u['username'] == 'external_user')
        assert ext_user_data['first_name'] == 'External'
        assert ext_user_data['last_name'] == 'Member'
        assert ext_user_data['email'] == 'external@test.com'
