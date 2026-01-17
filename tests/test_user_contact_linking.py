import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Contact, Club, ContactClub, AuthRole
from app.auth.permissions import Permissions

class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SERVER_NAME = 'localhost.localdomain'
    SECRET_KEY = 'test'

@pytest.fixture
def test_app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        # Seed roles
        if not AuthRole.query.filter_by(name='User').first():
            db.session.add(AuthRole(name='User', description='User role'))
        if not AuthRole.query.filter_by(name='SysAdmin').first():
            db.session.add(AuthRole(name='SysAdmin', description='System Administrator', level=100))
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def test_client(test_app):
    return test_app.test_client()

@pytest.fixture
def admin_user(test_app):
    """Create and login an admin user"""
    with test_app.app_context():
        # Create permissions/roles logic requires roles to be set up
        # We need a user with SETTINGS_VIEW_ALL permission to access these routes
        
        # Typically handled by role permissions. 
        # For simplicity in this mock DB, let's assume SysAdmin has all permissions
        sysadmin_role = AuthRole.query.filter_by(name='SysAdmin').first()
        
        # Create admin contact
        contact = Contact(Name='Admin User', Email='admin@test.com')
        db.session.add(contact)
        db.session.commit()

        user = User(username='admin', email='admin@test.com')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        
        # Assign SysAdmin role (mechanics depend on app implementation, usually via UserClub)
        # Assuming current logic uses UserClub
        from app.models import UserClub
        club = Club(club_no='0000', club_name='Test Club')
        db.session.add(club)
        db.session.commit()
        
        uc = UserClub(user_id=user.id, club_id=club.id, club_role_id=sysadmin_role.id, contact_id=contact.id)
        db.session.add(uc)
        db.session.commit()
        
        return user.id, club.id

def test_link_existing_contact(test_app, test_client, admin_user):
    """Test creating a new user linked to an existing contact."""
    user_id, club_id = admin_user
    
    # Login as admin
    test_client.post('/login', data={'username': 'admin', 'password': 'password'})
    
    with test_app.app_context():
        # Create an existing contact
        contact = Contact(Name='Existing Contact', Email='existing@test.com')
        db.session.add(contact)
        db.session.commit()
        contact_id = contact.id
        
        # Ensure context has current club
        with test_client.session_transaction() as sess:
            sess['current_club_id'] = club_id

        # POST to create user linked to this contact
        role = AuthRole.query.filter_by(name='User').first()
        
        response = test_client.post('/user/form', data={
            'username': 'linkeduser',
            'full_name': 'Existing Contact',
            'email': 'existing@test.com', # Should match
            'contact_id': contact_id,
            'roles': [role.id], 
            'password': 'Password123!',
            'status': 'active'
            # create_new_contact is omitted (False)
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        # Verify user created and linked
        new_user = User.query.filter_by(username='linkeduser').first()
        assert new_user is not None
        
        # Check link via club-aware method
        contact = new_user.get_contact(club_id)
        assert contact is not None
        assert contact.id == contact_id
        
        # Verify NO new contact created (count should be 2: Admin + Existing)
        assert Contact.query.count() == 2
        assert contact.Name == 'Existing Contact'

def test_create_new_contact_explicitly(test_app, test_client, admin_user):
    """Test creating a new user with a NEW contact (contact_id=0/None)."""
    user_id, club_id = admin_user
    
    # Login as admin
    test_client.post('/login', data={'username': 'admin', 'password': 'password'})
    
    with test_app.app_context():
        # Ensure context has current club
        with test_client.session_transaction() as sess:
            sess['current_club_id'] = club_id
            
        role = AuthRole.query.filter_by(name='User').first()

        response = test_client.post('/user/form', data={
            'username': 'newuser',
            'full_name': 'New User Contact',
            'email': 'new@test.com',
            'contact_id': 0, # Or empty
            'roles': [role.id],
            'password': 'Password123!',
            'status': 'active'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        # Verify user created
        new_user = User.query.filter_by(username='newuser').first()
        assert new_user is not None
        
        # Verify NEW contact created and linked via club
        contact = new_user.get_contact(club_id)
        assert contact is not None
        assert contact.Name == 'New User Contact'
        
        # Check contact count (Admin + New User = 2)
        assert Contact.query.count() == 2 
