import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Contact, Club, ContactClub, AuthRole, UserClub
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
            db.session.add(AuthRole(name='User', description='User role', level=1))
        if not AuthRole.query.filter_by(name='SysAdmin').first():
            db.session.add(AuthRole(name='SysAdmin', description='System Administrator', level=100))
        
        # Ensure ALL roles have levels for bitwise safety
        for r in AuthRole.query.all():
            if r.level is None:
                r.level = 0
            
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
        club = Club(club_no='0000', club_name='Test Club')
        db.session.add(club)
        db.session.commit()
        
        uc = UserClub(user_id=user.id, club_id=club.id, club_role_level=sysadmin_role.level, contact_id=contact.id)
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
        db.session.flush()
        contact_id = contact.id
        
        # LINK it to the club so isolation check passes
        db.session.add(ContactClub(contact_id=contact_id, club_id=club_id))
        db.session.commit()
        
        # Ensure context has current club
        with test_client.session_transaction() as sess:
            sess['current_club_id'] = club_id

        # POST to create user linked to this contact
        role = AuthRole.query.filter_by(name='User').first()
        
        response = test_client.post(f'/user/form?club_id={club_id}', data={
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
        # Note: admin_user fixture creates 1 contact.
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

        response = test_client.post(f'/user/form?club_id={club_id}', data={
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

def test_user_multiple_clubs_linked_contacts(test_app):
    """Verify that a user is linked to exactly one contact for each club they belong to."""
    with test_app.app_context():
        # 1. Setup two clubs
        club1 = Club(club_no='111', club_name='Club 1')
        club2 = Club(club_no='222', club_name='Club 2')
        db.session.add_all([club1, club2])
        db.session.commit()
        
        # 2. Setup user
        user = User(username='multi_club_user', email='multi@test.com')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        
        # 3. Join club1 and ensure contact
        contact1 = user.ensure_contact(full_name='User Club 1', club_id=club1.id)
        db.session.commit()
        
        # 4. Join club2 and ensure contact (with same email)
        # This should REUSE contact1 but update the name
        contact2 = user.ensure_contact(full_name='User Club 2', club_id=club2.id)
        db.session.commit()
        
        # 5. Verify memberships
        memberships = UserClub.query.filter_by(user_id=user.id).all()
        assert len(memberships) == 2
        
        # 6. Verify each membership has exactly one contact
        for uc in memberships:
            assert uc.contact_id is not None
            # Verify the contact exists
            contact = db.session.get(Contact, uc.contact_id)
            assert contact is not None
            
        # 7. Verify they have DIFFERENT contacts because of isolation design
        c1_contact = user.get_contact(club1.id)
        c2_contact = user.get_contact(club2.id)
        
        assert c1_contact.id != c2_contact.id
        assert c1_contact.Name == 'User Club 1' # Should NOT be synced if isolated
        assert c2_contact.Name == 'User Club 2'
        club3 = Club(club_no='333', club_name='Club 3')
        db.session.add(club3)
        db.session.commit()
        
        contact3 = user.ensure_contact(full_name='Separate Contact', email='other@test.com', club_id=club3.id)
        db.session.commit()
        
        assert contact3.id != c1_contact.id
        assert user.get_contact(club3.id).Name == 'Separate Contact'
        assert user.get_contact(club1.id).Name == 'User Club 1' # Unchanged

        # 9. Ensure that calling ensure_contact again stays 1:1
        updated_c3 = user.ensure_contact(full_name='Updated Separate', email='other@test.com', club_id=club3.id)
        db.session.commit()
        
        assert updated_c3.id == contact3.id
        assert updated_c3.Name == 'Updated Separate'
        assert UserClub.query.filter_by(user_id=user.id, club_id=club3.id).count() == 1
