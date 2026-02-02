import pytest
from unittest.mock import patch
from app.models import db, Contact, Vote, ExComm, ContactClub
from datetime import date

def test_create_and_delete_guest_contact(client, app, default_club):
    """
    Verifies that a guest contact can be created and then deleted using route functions.
    """
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    unique_name = f'Test Guest {unique_id}'

    # 0. Create User for Login
    from app.models import User
    with app.app_context():
        if not User.query.get(1):
            user = User(id=1, email='test@example.com', username='testuser')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()

    # 1. Setup Session
    with client.session_transaction() as sess:
        sess['_user_id'] = '1'
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True

    # Patch authorization to allow contact management
    with patch('app.contacts_routes.is_authorized', return_value=True):
        # 2. Create Guest Contact
        create_resp = client.post(
            '/contact/form',
            data={
                'first_name': 'Test',
                'last_name': f'Guest {unique_id}',
                'name': unique_name,
                'type': 'Guest',
                'email': f'testguest_{unique_id}@example.com'
            },
            follow_redirects=True
        )
        assert create_resp.status_code == 200
        # Check for success message to ensure creation actually happened
        if b'Contact added successfully' not in create_resp.data:
            print(f"Creation failed. Response: {create_resp.data}")
        assert b'Contact added successfully' in create_resp.data
        
        # Verify contact exists in DB
        with app.app_context():
            contact = Contact.query.filter_by(Name=unique_name).first()
            assert contact is not None
            assert contact.Type == 'Guest'
            contact_id = contact.id

        # 3. Delete Guest Contact
        delete_resp = client.post(
            f'/contact/delete/{contact_id}',
            follow_redirects=True
        )
        assert delete_resp.status_code == 200
        
        # Verify contact is deleted from DB
        with app.app_context():
            contact = db.session.get(Contact, contact_id)
            assert contact is None

def test_delete_guest_contact_with_references(client, app, default_club):
    """
    Verifies that a guest contact with references in Votes and ExComm can be deleted.
    This specifically tests the fix for the IntegrityError bug.
    """
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    unique_name = f'Reference Guest {unique_id}'
    unique_name = f'Reference Guest {unique_id}'
    voter_id = f'voter_{unique_id}'

    # 0. Create User for Login
    from app.models import User
    with app.app_context():
        if not User.query.get(1):
            user = User(id=1, email='test@example.com', username='testuser')
            user.set_password('password')
            db.session.add(user)
            db.session.commit()

    with app.app_context():
        # 1. Manually create a Guest Contact and references
        contact = Contact(Name=unique_name, Type='Guest')
        db.session.add(contact)
        db.session.flush()
        contact_id = contact.id
        
        # Associate with club
        cc = ContactClub(contact_id=contact_id, club_id=default_club.id)
        db.session.add(cc)
        
        # Create a Vote for the contact
        vote = Vote(meeting_number=1, voter_identifier=voter_id, contact_id=contact_id)
        db.session.add(vote)
        
        # Create an ExComm association via ExcommOfficer
        from app.models.roster import MeetingRole
        from app.models.excomm_officer import ExcommOfficer
        
        # Ensure a role exists for the test
        role = MeetingRole.query.filter_by(name='President').first()
        if not role:
            role = MeetingRole(name='President', type='officer', needs_approval=True, has_single_owner=True)
            db.session.add(role)
            db.session.flush()

        excomm = ExComm(club_id=default_club.id, excomm_term=f'26H_{unique_id}')
        db.session.add(excomm)
        db.session.flush()

        officer_link = ExcommOfficer(excomm_id=excomm.id, contact_id=contact_id, meeting_role_id=role.id)
        db.session.add(officer_link)
        db.session.commit()

    # 2. Setup Session
    with client.session_transaction() as sess:
        sess['_user_id'] = '1'
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True

    # 3. Delete Guest Contact via route
    with patch('app.contacts_routes.is_authorized', return_value=True):
        delete_resp = client.post(
            f'/contact/delete/{contact_id}',
            follow_redirects=True
        )
        assert delete_resp.status_code == 200
        
        # 4. Verify everything is cleaned up
        with app.app_context():
            # Contact should be gone
            assert db.session.get(Contact, contact_id) is None
            
            # Vote reference should be NULL
            vote = Vote.query.filter_by(voter_identifier=voter_id).first()
            assert vote.contact_id is None
            
            # ExComm reference should be gone from association table
            from app.models.excomm_officer import ExcommOfficer
            officer_link = ExcommOfficer.query.filter_by(contact_id=contact_id).first()
            assert officer_link is None
