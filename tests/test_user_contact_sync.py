import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Contact, Club, AuthRole, UserClub, ContactClub
from sqlalchemy import event

class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'test'

@pytest.fixture
def test_app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        # Seed roles
        db.session.add(AuthRole(name='User', description='User role', level=1))
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()

def test_user_creation_from_existing_contact(test_app):
    """Test that creating a user from an existing contact copies names to User."""
    with test_app.app_context():
        club = Club(club_no='123', club_name='Test Club')
        db.session.add(club)
        db.session.commit()

        # Create contact with names
        contact = Contact(
            Name='John Doe',
            first_name='John',
            last_name='Doe',
            Email='john@example.com',
            Type='Member'
        )
        db.session.add(contact)
        db.session.flush() # Get contact ID
        db.session.add(ContactClub(contact_id=contact.id, club_id=club.id))
        db.session.commit()

        # Create user linked to this contact via ensure_contact
        user = User(username='johndoe', email='john@example.com')
        user.set_password('password')
        db.session.add(user)
        db.session.flush()

        # This should trigger the copy in ensure_contact
        user.ensure_contact(club_id=club.id)
        db.session.commit()

        assert user.first_name == 'John'
        assert user.last_name == 'Doe'

def test_user_creation_new_contact(test_app):
    """Test that creating a new user also creates a contact with matching names."""
    with test_app.app_context():
        club = Club(club_no='123', club_name='Test Club')
        db.session.add(club)
        db.session.commit()

        user = User(
            username='newuser',
            first_name='New',
            last_name='User',
            email='new@example.com'
        )
        user.set_password('password')
        db.session.add(user)
        db.session.flush()

        # This should create a new contact
        contact = user.ensure_contact(
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            club_id=club.id
        )
        db.session.commit()

        assert contact is not None
        assert contact.first_name == 'New'
        assert contact.last_name == 'User'
        assert contact.Name == 'New User'

def test_name_sync_user_to_contact(test_app):
    """Test that updating User names updates the linked Contact."""
    with test_app.app_context():
        club = Club(club_no='123', club_name='Test Club')
        db.session.add(club)
        db.session.commit()

        user = User(
            username='syncuser',
            first_name='Original',
            last_name='Name',
            email='sync@example.com'
        )
        user.set_password('password')
        db.session.add(user)
        db.session.flush()
        
        contact = user.ensure_contact(
            first_name=user.first_name,
            last_name=user.last_name,
            club_id=club.id
        )
        db.session.commit()

        # Update User names
        user.first_name = 'Updated'
        user.last_name = 'Name'
        db.session.commit()

        # Refresh contact
        db.session.refresh(contact)
        assert contact.first_name == 'Updated'
        assert contact.Name == 'Updated Name'

def test_save_user_data_sync(test_app):
    """Test _save_user_data flow (integration test)."""
    from app.users_routes import _save_user_data
    with test_app.app_context():
        club = Club(club_no='123', club_name='Test Club')
        db.session.add(club)
        db.session.commit()

        # Create user via _save_user_data
        from unittest.mock import patch
        with patch('app.users_routes.is_authorized', return_value=True):
            user = _save_user_data(
                username='flowuser',
                first_name='Flow',
                last_name='User',
                email='flow@example.com',
                club_id=club.id
            )
        db.session.commit()

        user_id = user.id

        assert user.first_name == 'Flow'
        assert user.last_name == 'User'
        
        contact = user.get_contact(club.id)
        assert contact.first_name == 'Flow'
        assert contact.Name == 'Flow User'

        # UPDATE using _save_user_data
        # We need to re-fetch or ensure target is in session
        from unittest.mock import patch
        user = db.session.get(User, user_id)
        with patch('app.users_routes.is_authorized', return_value=True):
            _save_user_data(
                user=user,
                first_name='UpdatedFlow',
                club_id=club.id
            )
        db.session.commit()

        assert user.first_name == 'UpdatedFlow'
        db.session.refresh(contact)
        assert contact.first_name == 'UpdatedFlow'
        assert contact.Name == 'UpdatedFlow User'



def test_profile_update_sync(test_app):
    """Test updating names via the profile route simulation."""
    with test_app.app_context():
        club = Club(club_no='123', club_name='Test Club')
        db.session.add(club)
        db.session.commit()

        user = User(
            username='profileuser',
            first_name='Original',
            last_name='Name',
            email='profile@example.com'
        )
        user.set_password('password')
        db.session.add(user)
        db.session.flush()
        
        contact = user.ensure_contact(
            first_name=user.first_name,
            last_name=user.last_name,
            club_id=club.id
        )
        db.session.commit()

        # Simulate profile update logic from auth/routes.py
        user.first_name = 'NewFirst'
        user.last_name = 'NewLast'
        db.session.commit()

        # Refresh contact
        db.session.refresh(contact)
        assert contact.first_name == 'NewFirst'
        assert contact.last_name == 'NewLast'
        assert contact.Name == 'NewFirst NewLast'

def test_club_admin_restriction(test_app):
    """Test that ClubAdmin cannot update restricted fields for existing users."""
    from app.users_routes import _save_user_data
    from unittest.mock import patch

    with test_app.app_context():
        club = Club(club_no='123', club_name='Test Club')
        db.session.add(club)
        db.session.commit()

        user = User(
            username='limiteduser',
            first_name='Original',
            last_name='Name',
            email='limited@example.com'
        )
        user.set_password('password')
        db.session.add(user)
        db.session.commit()

        # 1. Simulate ClubAdmin (is_authorized returns False for SYSADMIN)
        with patch('app.users_routes.is_authorized', return_value=False):
            _save_user_data(
                user=user,
                first_name='AttemptedUpdate',
                email='hacked@example.com',
                club_id=club.id
            )
            db.session.commit()
            
            # Should NOT be updated
            assert user.first_name == 'Original'
            assert user.email == 'limited@example.com'

        # 2. Simulate SysAdmin (is_authorized returns True)
        with patch('app.users_routes.is_authorized', return_value=True):
            _save_user_data(
                user=user,
                first_name='SysAdminUpdate',
                email='admin@example.com',
                club_id=club.id
            )
            db.session.commit()
            
            # SHOULD be updated
            assert user.first_name == 'SysAdminUpdate'
            assert user.email == 'admin@example.com'


