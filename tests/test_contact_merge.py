import pytest
from app import db
from app.models import Contact, Roster, ContactClub, Achievement, UserClub, Club, Meeting
from datetime import date

from unittest.mock import patch

def test_merge_contacts_logic(app, client, default_club):
    """Test the core merge_contacts logic in Contact model."""
    with app.app_context():
        # 1. Setup Contacts
        c1 = Contact(Name="Primary Member", Type="Member", Date_Created=date(2020, 1, 1))
        c2 = Contact(Name="Secondary Guest", Type="Guest", Date_Created=date(2021, 1, 1))
        c3 = Contact(Name="Another Guest", Type="Guest", Date_Created=date(2022, 1, 1))
        
        db.session.add_all([c1, c2, c3])
        db.session.commit()
        
        c1_id, c2_id, c3_id = c1.id, c2.id, c3.id

        # 2. Setup related data
        # Membership
        db.session.add(ContactClub(contact_id=c1_id, club_id=default_club.id))
        db.session.add(ContactClub(contact_id=c2_id, club_id=default_club.id))
        
        # Roster
        r1 = Roster(contact_id=c2_id, meeting_number=100)
        db.session.add(r1)
        
        # Meeting Award
        m1 = Meeting(club_id=default_club.id, Meeting_Number=101, best_table_topic_id=c2_id)
        db.session.add(m1)
        
        # Achievement
        a1 = Achievement(contact_id=c3_id, achievement_type='level-completion', issue_date=date.today())
        db.session.add(a1)
        
        db.session.commit()
        
        # 3. Perform Merge
        Contact.merge_contacts(c1_id, [c2_id, c3_id])
        
        # 4. Verify
        # Need to expire to see changes after bulk delete/update
        db.session.expire_all()
        
        # Secondary contacts deleted
        assert db.session.get(Contact, c2_id) is None
        assert db.session.get(Contact, c3_id) is None
        
        # Roster updated
        updated_r1 = Roster.query.filter_by(meeting_number=100).first()
        assert updated_r1.contact_id == c1_id
        
        # Meeting award updated
        updated_m1 = Meeting.query.filter_by(Meeting_Number=101).first()
        assert updated_m1.best_table_topic_id == c1_id
        
        # Achievement updated
        updated_a1 = Achievement.query.filter_by(achievement_type='level-completion').first()
        assert updated_a1.contact_id == c1_id
        
        # Membership consolidated (no duplicate)
        memberships = ContactClub.query.filter_by(contact_id=c1_id).all()
        assert len(memberships) == 1

def test_merge_route_permissions(client):
    """Test that merge route requires appropriate permissions."""
    # Test without login
    response = client.post('/contacts/merge', json={'contact_ids': [1, 2]})
    assert response.status_code == 302 # Redirect to login

def test_merge_route_primary_selection(app, client, default_club, user1):
    """Test that the route correctly identifies the primary contact."""
    with app.app_context():
        # Ensure user1 is in default_club with a role
        uc = UserClub.query.filter_by(user_id=user1.id, club_id=default_club.id).first()
        if not uc:
            uc = UserClub(user_id=user1.id, club_id=default_club.id, club_role_level=1)
            db.session.add(uc)
        else:
            uc.club_role_level = 1
        
        # Member vs Guest
        c1 = Contact(Name="Old Guest", Type="Guest", Date_Created=date(2010, 1, 1))
        c2 = Contact(Name="New Member", Type="Member", Date_Created=date(2023, 1, 1))
        db.session.add_all([c1, c2])
        db.session.commit()
        
        ids = [c1.id, c2.id]
        c1_id = c1.id
        
    # Simulate Login
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user1.id)
        sess['current_club_id'] = default_club.id
        sess['_fresh'] = True
        
    with patch('app.contacts_routes.is_authorized', return_value=True):
        response = client.post('/contacts/merge', json={'contact_ids': ids})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        # Primary should be c2 (Member) even if newer
        assert data['primary_id'] == c2.id
        
        with app.app_context():
            # Verify c1 is gone
            assert db.session.get(Contact, c1_id) is None
