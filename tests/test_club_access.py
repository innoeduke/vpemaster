import pytest
from flask import session
from app.models import db, Club, Contact, ContactClub, User, AuthRole, Permission
from app.club_context import authorized_club_required
from flask_login import login_user
from datetime import datetime

@pytest.fixture(autouse=True)
def cleanup_db(app):
    """Cleanup specific test data after each test."""
    yield
    with app.app_context():
        # Order matters for foreign keys
        ContactClub.query.filter(ContactClub.membership_type == 'TestMembership').delete()
        User.query.filter(User.Username.in_(['admin_test', 'member_test', 'restricted_test'])).delete()
        Contact.query.filter(Contact.Name.in_(['Admin User', 'Member User', 'Restricted User'])).delete()
        Club.query.filter(Club.club_no.in_(['C1', 'C2', 'C3', 'C4', 'C5'])).delete()
        db.session.commit()

def test_admin_access_any_club(app, client):
    """Test that a SysAdmin can access any club."""
    with app.app_context():
        # 1. Setup - Create an Admin user
        admin_user = User.query.filter_by(Username='admin_test').first()
        if not admin_user:
            admin_user = User(Username='admin_test', Status='active')
            admin_user.set_password('password')
            db.session.add(admin_user)
            
            admin_role = AuthRole.query.filter_by(name='SysAdmin').first()
            if not admin_role:
                admin_role = AuthRole(name='SysAdmin', level=8)
                db.session.add(admin_role)
            db.session.flush()
            admin_user.add_role(admin_role)
            db.session.commit()

        # 2. Setup - Create a club
        club = Club(club_no='C1', club_name='Club 1')
        db.session.add(club)
        db.session.commit()

        # 3. Test - Login as admin
        with client.session_transaction() as sess:
            sess['current_club_id'] = club.id
        
        login_user(admin_user)
        
        # Define a dummy function decorated with authorized_club_required
        @authorized_club_required
        def dummy_view():
            return "Success"

        # Call the dummy function
        assert dummy_view() == "Success"

def test_member_access_authorized_club(app, client):
    """Test that a member can access their authorized club."""
    with app.app_context():
        # 1. Setup - Create a member user and a club
        club = Club(club_no='C2', club_name='Club 2')
        db.session.add(club)
        db.session.flush()
        
        contact = Contact(Name='Member User', Type='Member')
        db.session.add(contact)
        db.session.flush()
        
        user = User(Username='member_test', Status='active', Contact_ID=contact.id)
        user.set_password('password')
        db.session.add(user)
        
        membership = ContactClub(contact_id=contact.id, club_id=club.id, membership_type='TestMembership')
        db.session.add(membership)
        db.session.commit()

        # 2. Test - Login as member and set club context
        with client.session_transaction() as sess:
            sess['current_club_id'] = club.id
        
        login_user(user)
        
        @authorized_club_required
        def dummy_view():
            return "Success"

        assert dummy_view() == "Success"

def test_member_denied_unauthorized_club(app, client):
    """Test that a member is denied access to a club they don't belong to."""
    from werkzeug.exceptions import Forbidden
    
    with app.app_context():
        # 1. Setup - Create a member user and two clubs
        club1 = Club(club_no='C3', club_name='Club 3')
        club2 = Club(club_no='C4', club_name='Club 4')
        db.session.add_all([club1, club2])
        db.session.flush()
        
        contact = Contact(Name='Restricted User', Type='Member')
        db.session.add(contact)
        db.session.flush()
        
        user = User(Username='restricted_test', Status='active', Contact_ID=contact.id)
        user.set_password('password')
        db.session.add(user)
        
        # Only belongs to club1
        membership = ContactClub(contact_id=contact.id, club_id=club1.id, membership_type='TestMembership')
        db.session.add(membership)
        db.session.commit()

        # 2. Test - Login as member but set context to club2
        with client.session_transaction() as sess:
            sess['current_club_id'] = club2.id
        
        login_user(user)
        
        @authorized_club_required
        def dummy_view():
            return "Success"

        with pytest.raises(Forbidden):
            dummy_view()

def test_guest_access_with_permission(app, client):
    """Test that an anonymous guest can access a club if they have ABOUT_CLUB_VIEW."""
    with app.app_context():
        # 1. Setup - Create a club and Guest role with permission
        club = Club(club_no='C5', club_name='Club 5')
        db.session.add(club)
        
        guest_role = AuthRole.query.filter_by(name='Guest').first()
        if not guest_role:
            guest_role = AuthRole(name='Guest', level=0)
            db.session.add(guest_role)
            
        perm = Permission.query.filter_by(name='ABOUT_CLUB_VIEW').first()
        if not perm:
            perm = Permission(name='ABOUT_CLUB_VIEW', category='Club')
            db.session.add(perm)
        db.session.flush()
        
        # Ensure permission is attached to role
        if perm not in guest_role.permissions:
            guest_role.permissions.append(perm)
            
        db.session.commit()

        # 2. Test - Set club context and access as guest (no login_user)
        with client.session_transaction() as sess:
            sess['current_club_id'] = club.id
        
        @authorized_club_required
        def dummy_view():
            return "Success"

        # This should succeed as AnonymousUser has Guest permissions
        assert dummy_view() == "Success"
