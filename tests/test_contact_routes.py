import pytest
from unittest.mock import patch
from app.models import db, User, Contact, UserClub, ContactClub

def test_contact_form_joinedload_bug(client, app, default_club):
    """
    Verify that contact_form/<id> does not crash with NameError (500)
    when the contact is linked to a user.
    """
    with app.app_context():
        # 1. Setup Data
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        u = User(username=f'bugverified_{unique_id}', email=f'bug_{unique_id}@verified.com')
        u.set_password('pass')
        db.session.add(u)
        
        c = Contact(Name=f'Bug Contact {unique_id}', Type='Member', Email=f'bug_{unique_id}@contact.com')
        db.session.add(c)
        db.session.commit()
        
        uc = UserClub(user_id=u.id, contact_id=c.id, club_id=default_club.id, is_home=True)
        cc = ContactClub(contact_id=c.id, club_id=default_club.id)
        db.session.add(uc)
        db.session.add(cc)
        db.session.commit()
        
        contact_id = c.id
        user_id = u.id

    # 2. Simulate Login & Session
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True

    # 3. Patch permissions to allow access
    with patch('app.contacts_routes.is_authorized', return_value=True):
        # 4. Make request
        resp = client.get(f'/contact/form/{contact_id}')
        
        # 5. Assert
        # If the bug is present, this will be 500
        assert resp.status_code == 200, f"Expected 200 OK, got {resp.status_code}. Data: {resp.data}"
        
        json_data = resp.get_json()
        assert json_data is not None
        assert json_data['contact']['id'] == contact_id
        # We also expect 'user_clubs' to be populated because we set up UserClub
        assert len(json_data['user_clubs']) > 0

def test_contact_update_no_flash_on_ajax(client, app, default_club, user1):
    """Verify that an AJAX update does NOT produce a flash message."""
    with app.app_context():
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        unique_name = f'Flash Test {unique_id}'
        c = Contact(Name=unique_name, Type='Guest')
        db.session.add(c)
        db.session.commit()
        contact_id = c.id
        user_id = user1.id

    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True

    with patch('app.contacts_routes.is_authorized', return_value=True):
        # AJAX request
        resp = client.post(
            f'/contact/form/{contact_id}',
            data={
                'first_name': 'Flash', 
                'last_name': 'Test', 
                'name': unique_name 
            },
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert resp.status_code == 200
        
        # Check flash messages in session
        with client.session_transaction() as sess:
            # flash messages are stored in '_flashes'
            flashes = sess.get('_flashes', [])
            assert not any(f[1] == 'Contact updated successfully!' for f in flashes)

def test_contact_update_has_flash_on_standard_request(client, app, default_club, user1):
    """Verify that a standard (non-AJAX) update STILL produces a flash message."""
    with app.app_context():
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        unique_name = f'Standard Test {unique_id}'
        c = Contact(Name=unique_name, Type='Guest')
        db.session.add(c)
        db.session.commit()
        contact_id = c.id

    with client.session_transaction() as sess:
        sess['_user_id'] = str(user1.id)
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True

    with patch('app.contacts_routes.is_authorized', return_value=True):
        # Standard request (no X-Requested-With)
        resp = client.post(
            f'/contact/form/{contact_id}',
            data={
                'first_name': 'Standard', 
                'last_name': 'Test', 
                'name': unique_name
            }
        )
        assert resp.status_code == 302 # Redirects to show_contacts
        
        # Check flash messages in session
        with client.session_transaction() as sess:
            flashes = sess.get('_flashes', [])
            assert any(f[1] == 'Contact updated successfully!' for f in flashes)


def test_contact_search_includes_phone(client, app, default_club):
    """Verify that search results include the Phone_Number field."""
    with app.app_context():
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        phone = "1234567890"
        c = Contact(Name=f'Search Test {unique_id}', Type='Guest', Phone_Number=phone)
        db.session.add(c)
        db.session.commit()
        
        cc = ContactClub(contact_id=c.id, club_id=default_club.id)
        db.session.add(cc)
        db.session.commit()
        
        contact_name = c.Name
        
        # Create a user for authentication
        from app.models import User
        u = User(username=f'search_tester_{unique_id}', email=f'tester_{unique_id}@example.com')
        u.set_password('pass')
        db.session.add(u)
        db.session.commit()
        user_id = u.id

        # Add user to club to satisfy @authorized_club_required
        from app.models import UserClub
        uc = UserClub(user_id=u.id, club_id=default_club.id, club_role_level=1)
        db.session.add(uc)
        db.session.commit()

    with client.session_transaction() as sess:
        sess['_user_id'] = str(user_id)
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True

    with patch('app.contacts_routes.is_authorized', return_value=True):
        resp = client.get(f'/contacts/search?q={contact_name}')
        assert resp.status_code == 200
        data = resp.get_json()
        
        assert len(data) > 0
        found = False
        for item in data:
            if item['Name'] == contact_name:
                assert 'Phone_Number' in item
                assert item['Phone_Number'] == phone
                found = True
                break
        assert found
