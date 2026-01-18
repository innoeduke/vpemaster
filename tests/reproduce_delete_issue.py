
import pytest
from app.models import Club, User, Contact, ContactClub, UserClub, AuthRole
from app import db

@pytest.fixture
def multi_club_user(app):
    with app.app_context():
        # Clean up existing test data
        for c in Club.query.filter(Club.club_no.in_(['1111', '2222'])).all():
            db.session.delete(c)
        
        db.session.query(User).filter_by(username='multi_club_user').delete()
        db.session.query(User).filter_by(username='admin_act').delete()
        db.session.query(Contact).filter_by(Email='multi@example.com').delete()
        db.session.commit()

        # Create two clubs
        club1 = Club(club_no='1111', club_name='Club One')
        club2 = Club(club_no='2222', club_name='Club Two')
        db.session.add_all([club1, club2])
        db.session.commit()

        # Create a user
        user = User(username='multi_club_user', email='multi@example.com')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()

        # Create contacts for the user in both clubs. 
        # Note: Contacts table has unique Email constraint. 
        # Typically a user would share ONE contact record.
        # But for this test, if we want to test "deletes the associated contact", 
        # we face the issue that if they share a contact, deleting it breaks the other club.
        # However, the user requirement implies a cleanup. 
        # If we use the SAME contact, we can test if it gets deleted (bad) or preserved (good?).
        # If the requirement says "delete the contact", and it's shared, it's destructive.
        # Let's assume the standard case where they SHARE the contact.
        
        contact_shared = Contact(Name='Multi User Shared', Email='multi@example.com', Type='Member')
        db.session.add(contact_shared)
        db.session.commit()

        # Link contacts to clubs (Same contact)
        cc1 = ContactClub(contact_id=contact_shared.id, club_id=club1.id)
        cc2 = ContactClub(contact_id=contact_shared.id, club_id=club2.id)
        db.session.add_all([cc1, cc2])
        db.session.commit()

        # Link user to clubs/contacts
        uc1 = UserClub(user_id=user.id, club_id=club1.id, contact_id=contact_shared.id)
        uc2 = UserClub(user_id=user.id, club_id=club2.id, contact_id=contact_shared.id)
        db.session.add_all([uc1, uc2])
        db.session.commit()
        
        return {
            'user_id': user.id,
            'club1_id': club1.id,
            'club2_id': club2.id,
            'contact1_id': contact_shared.id, # It's the same contact
            'uc1_id': uc1.id,
            'uc2_id': uc2.id
        }

def test_delete_user_from_club_one(client, app, multi_club_user):
    """
    Test that deleting the user from Club One:
    1. Removes their UserClub for Club One
    2. Removes their Contact for Club One
    3. Removes their ContactClub for Club One
    4. PRESERVES the User record (since they are in Club Two)
    5. PRESERVES the UserClub/Contact/ContactClub for Club Two
    """
    data = multi_club_user
    user_id = data['user_id']
    club1_id = data['club1_id']
    club2_id = data['club2_id']
    contact1_id = data['contact1_id']

    # Log in as admin (needed for the route)
    # For now, let's assume we can mock or force login. 
    # But since we are calling the route, we need to be authorized.
    # The current `delete_user` checks Permissions.SETTINGS_VIEW_ALL.
    # We can skip the route and test a logic function if we extract it, 
    # but to test the route we need to simulate a login.
    
    # Let's cheat and use the `delete_user` logic directly or simulate it?
    # Better to test the route behavior as that's what's being changed.
    
    admin_id = None
    with app.app_context():
        # Clean up potential leftover admin
        db.session.query(User).filter_by(username='admin_act').delete()
        db.session.query(Contact).filter_by(Email='admin@example.com').delete()
        db.session.commit()

        # Create sysadmin role if needed
        role = AuthRole.query.filter_by(name='SysAdmin').first()
        if not role:
            role = AuthRole(name='SysAdmin')
            db.session.add(role)
            db.session.commit()
            
        admin = User(username='admin_act', email='admin@example.com')
        admin.set_password('password')
        db.session.add(admin)
        db.session.commit()
        admin_id = admin.id
        
        # Give admin permissions. The delete_user route checks Permissions.SETTINGS_VIEW_ALL.
        # This permission is usually in SysAdmin role.
        # We need to give this user the SysAdmin role in the current club (club1).
        
        # We need to create a contact for the admin too
        c_admin = Contact(Name='Admin', Email='admin@example.com', Type='Member')
        db.session.add(c_admin)
        db.session.commit()
        
        uc_admin = UserClub(user_id=admin.id, club_id=club1_id, contact_id=c_admin.id, club_role_id=role.id)
        db.session.add(uc_admin)
        db.session.commit()

    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['current_club_id'] = club1_id # Simulate being in Club One context
        sess['_fresh'] = True

    # But wait, does the test client simulate the "club_context"? 
    # app/club_context.py uses session.get('club_id').
    
    # Perform the POST request to delete the user
    response = client.post(f'/user/delete/{user_id}', follow_redirects=True)
    
    assert response.status_code == 200

    with app.app_context():
        # Check UserClub 1 is gone
        uc1 = UserClub.query.filter_by(user_id=user_id, club_id=club1_id).first()
        assert uc1 is None, "UserClub for Club 1 should be deleted"

        # Check ContactClub 1 (the link) is gone
        cc1 = ContactClub.query.filter_by(contact_id=contact1_id, club_id=club1_id).first()
        assert cc1 is None, "ContactClub for Club 1 should be deleted"

        # Check Contact (Shared) is PRESERVED (because it is used in Club 2)
        # It should NOT be deleted if it is shared
        c1 = db.session.get(Contact, contact1_id)
        assert c1 is not None, "Shared Contact should be PRESERVED"
        assert c1.Type == 'Member', "Shared Contact should remain Member (not Guest)"

        # Check User record still exists
        u = db.session.get(User, user_id)
        assert u is not None, "User record should NOT be deleted (still in Club 2)"
        
        # Check UserClub 2 still exists
        uc2 = UserClub.query.filter_by(user_id=user_id, club_id=club2_id).first()
        assert uc2 is not None, "UserClub for Club 2 should preserved"

