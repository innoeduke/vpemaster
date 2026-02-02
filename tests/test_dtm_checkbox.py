import pytest
from unittest.mock import patch
from app.models import db, Contact, ContactClub

def test_add_guest_with_dtm(client, app, default_club, user1):
    """Verify that adding a guest with DTM checked saves the DTM status."""
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user1.id)
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True

    with patch('app.contacts_routes.is_authorized', return_value=True):
        # AJAX request to add guest
        resp = client.post(
            '/contact/form',
            data={
                'first_name': 'DTM', 
                'last_name': 'Guest', 
                'name': 'DTM Guest',
                'type': 'Guest',
                'dtm': 'on'  # Checkbox 'on' means checked in standard form post
            },
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['success'] is True
        
        contact_id = data['contact']['id']
        
        with app.app_context():
            contact = Contact.query.get(contact_id)
            assert contact.Name == 'DTM Guest'
            assert contact.DTM is True

def test_update_guest_dtm(client, app, default_club, user1):
    """Verify that updating a guest's DTM status works."""
    with app.app_context():
        c = Contact(Name='Update DTM Test', Type='Guest', DTM=False)
        db.session.add(c)
        db.session.commit()
        contact_id = c.id
        
        cc = ContactClub(contact_id=contact_id, club_id=default_club.id)
        db.session.add(cc)
        db.session.commit()

    with client.session_transaction() as sess:
        sess['_user_id'] = str(user1.id)
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True

    with patch('app.contacts_routes.is_authorized', return_value=True):
        # 1. Update to DTM=True
        resp = client.post(
            f'/contact/form/{contact_id}',
            data={
                'first_name': 'Update', 
                'last_name': 'DTM', 
                'name': 'Update DTM Test',
                'type': 'Guest',
                'dtm': 'on'
            },
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert resp.status_code == 200
        
        with app.app_context():
            contact = Contact.query.get(contact_id)
            assert contact.DTM is True

        # 2. Update to DTM=False (dtm field missing in post data)
        resp = client.post(
            f'/contact/form/{contact_id}',
            data={
                'first_name': 'Update', 
                'last_name': 'DTM', 
                'name': 'Update DTM Test',
                'type': 'Guest'
                # 'dtm' is missing
            },
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        assert resp.status_code == 200
        
        with app.app_context():
            contact = Contact.query.get(contact_id)
            assert contact.DTM is False
