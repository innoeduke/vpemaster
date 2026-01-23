
import pytest
from datetime import date
from app.models import Club, User, Contact, ContactClub, UserClub, Meeting, MeetingRole, Roster
from app.auth.permissions import Permissions
from app.models import AuthRole

@pytest.fixture
def auth_sysadmin(client, app):
    """Creates a SysAdmin user and logs them in."""
    with app.app_context():
        from app import db
        
        # Ensure SysAdmin role
        role = AuthRole.get_by_name(Permissions.SYSADMIN)
        if not role:
            role = AuthRole(name=Permissions.SYSADMIN, level=100)
            db.session.add(role)
            db.session.commit()
            
        # Create User
        user = User.query.filter_by(email='sysadmin_del_test@example.com').first()
        if not user:
            user = User(username='sysadmin_del', email='sysadmin_del_test@example.com')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()
            
        # Create Contact for User
        contact = Contact.query.filter_by(Email='sysadmin_del_test@example.com').first()
        if not contact:
            contact = Contact(Name='SysAdmin Delete', Email='sysadmin_del_test@example.com', Type='Member')
            db.session.add(contact)
            db.session.commit()
            
        # Link User-Contact (needed for permission checks often)
        # And give SysAdmin role
        # We need a dummy club for the SysAdmin to "be in" to have the role, 
        # or we rely on global check. The utils.py checks UserClub.
        
        club = Club.query.order_by(Club.id).first()
        if not club:
            club = Club(club_no='999999', club_name='System Club')
            db.session.add(club)
            db.session.commit()
            
        uc = UserClub.query.filter_by(user_id=user.id, club_id=club.id).first()
        if not uc:
            uc = UserClub(user_id=user.id, club_id=club.id, contact_id=contact.id, club_role_level=role.level)
            db.session.add(uc)
            db.session.commit()
            
    # Login
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True
        
    return user.id

def test_delete_club_complex_scenario(client, auth_sysadmin, app):
    """
    Test deleting a club verifies:
    1. Club is deleted.
    2. Associated Meetings are deleted.
    3. Orphan contacts (only in this club) are deleted.
    4. Shared contacts (in this and other clubs) are preserved.
    5. User accounts are preserved.
    """
    with app.app_context():
        from app import db
        
        db.session.commit()

        # Create Club to Delete
        club_to_delete = Club(club_no='DEL001', club_name='Delete Me Club')
        db.session.add(club_to_delete)
        
        # Create Safe Club (for shared contact)
        safe_club = Club(club_no='SAFE001', club_name='Safe Club')
        db.session.add(safe_club)
        db.session.commit()
        
        # Create Orphan Contact (Only in club_to_delete)
        orphan_contact = Contact(Name='Orphan Annie', Email='orphan@example.com', Type='Member')
        db.session.add(orphan_contact)
        db.session.commit()
        
        db.session.add(ContactClub(contact_id=orphan_contact.id, club_id=club_to_delete.id))
        
        # Create Shared Contact (In club_to_delete AND safe_club)
        shared_contact = Contact(Name='Shared Sam', Email='shared@example.com', Type='Member')
        db.session.add(shared_contact)
        db.session.commit()
        
        db.session.add(ContactClub(contact_id=shared_contact.id, club_id=club_to_delete.id))
        db.session.add(ContactClub(contact_id=shared_contact.id, club_id=safe_club.id))
        
        # Create User Linked Contact (In club_to_delete)
        # Users should NEVER be deleted, even if their contact link in this club is removed.
        linked_user = User(username='linked_user', email='linked@example.com')
        linked_user.set_password('pass')
        db.session.add(linked_user)
        db.session.commit()
        
        user_contact = Contact(Name='Linked Larry', Email='linked@example.com', Type='Member')
        db.session.add(user_contact)
        db.session.commit()
        
        # Link user to club (UserClub) and contact to club (ContactClub)
        db.session.add(UserClub(user_id=linked_user.id, club_id=club_to_delete.id, contact_id=user_contact.id))
        db.session.add(ContactClub(contact_id=user_contact.id, club_id=club_to_delete.id))
        
        # Create a Meeting for the club
        meeting = Meeting(club_id=club_to_delete.id, Meeting_Title='Last Meeting', Meeting_Date=date.today(), Meeting_Number=12345)
        db.session.add(meeting)
        db.session.commit()
        
        # Capture IDs for verification
        club_id = club_to_delete.id
        meeting_id = meeting.id
        orphan_id = orphan_contact.id
        shared_id = shared_contact.id
        user_id = linked_user.id
        user_contact_id = user_contact.id
        safe_club_id = safe_club.id  # Capture this too
        
        # 2. Execute Deletion
        # ---------------------------------------------------------
    
    # Needs to be outside app_context block to use client.post which handles its own context/session
    response = client.post(f'/clubs/{club_id}/delete', follow_redirects=True)
    assert response.status_code == 200
    if b'deleted successfully' not in response.data:
        # Try to find what error happened
        import re
        error_match = re.search(b'Error deleting club: ([^<]+)', response.data)
        if error_match:
            pytest.fail(f"Club deletion failed with: {error_match.group(1).decode()}")
        else:
             pytest.fail(f"Club deletion failed. Response content: {response.data[:200]}")
    
    # 3. Verify Results
    # ---------------------------------------------------------
    with app.app_context():
        from app import db
        
        # Club should be gone
        assert db.session.get(Club, club_id) is None
        
        # Meeting should be gone
        assert db.session.get(Meeting, meeting_id) is None
        
        # Orphan Contact should be gone (as it had no other memberships)
        assert db.session.get(Contact, orphan_id) is None
        
        # Shared Contact should still exist (as it is in Safe Club)
        assert db.session.get(Contact, shared_id) is not None
        # Link to deleted club gone?
        assert ContactClub.query.filter_by(contact_id=shared_id, club_id=club_id).first() is None
        # Link to safe club remains?
        assert ContactClub.query.filter_by(contact_id=shared_id, club_id=safe_club_id).first() is not None
        
        # User Account should still exist
        assert db.session.get(User, user_id) is not None
        
        assert db.session.get(Contact, user_contact_id) is None

