import pytest
from app import db
from app.models import Club, User, UserClub, MeetingRole
from app.models.voting import Award, AwardRole
from unittest.mock import patch

def login_user(client, user, club_id):
    with client.session_transaction() as sess:
        sess['user_id'] = user.id
        sess['_user_id'] = str(user.id)
        sess['club_id'] = club_id

def test_add_award_success(client, app, default_club, staff_user):
    with app.app_context():
        # Setup roles for association
        role1 = MeetingRole(name="Role 1", club_id=default_club.id, type='standard', needs_approval=False, has_single_owner=True)
        role2 = MeetingRole(name="Role 2", club_id=default_club.id, type='standard', needs_approval=False, has_single_owner=True)
        db.session.add_all([role1, role2])
        db.session.commit()
        role1_id = role1.id
        role2_id = role2.id

    login_user(client, staff_user, default_club.id)

    with patch('app.settings_routes.is_authorized', return_value=True):
        payload = {
            'name': 'Best Test Award',
            'category': 'best-test',
            'max_votes': 2,
            'max_winners': 2,
            'selected_role_ids': [role1_id, role2_id]
        }
        response = client.post('/api/settings/awards/add', json=payload)
        assert response.status_code == 200
        res_data = response.get_json()
        assert res_data['success'] is True
        assert 'added successfully' in res_data['message']
        award_id = res_data['award_id']

        # Verify in DB
        with app.app_context():
            award = db.session.get(Award, award_id)
            assert award is not None
            assert award.name == 'Best Test Award'
            assert award.category == 'best-test'
            assert award.max_votes_per_user == 2
            assert award.max_winners == 2
            assert len(award.role_associations) == 2
            assoc_role_ids = {a.meeting_role_id for a in award.role_associations}
            assert assoc_role_ids == {role1_id, role2_id}

def test_add_award_duplicate(client, app, default_club, staff_user):
    with app.app_context():
        award = Award(club_id=default_club.id, name='Existing', category='exist', max_votes_per_user=1, max_winners=1)
        db.session.add(award)
        db.session.commit()

    login_user(client, staff_user, default_club.id)

    with patch('app.settings_routes.is_authorized', return_value=True):
        payload = {
            'name': 'New Award Name',
            'category': 'exist',  # Duplicate category
            'max_votes': 1,
            'max_winners': 1,
            'selected_role_ids': []
        }
        response = client.post('/api/settings/awards/add', json=payload)
        assert response.status_code == 400
        res_data = response.get_json()
        assert res_data['success'] is False
        assert 'already exists' in res_data['message']

def test_update_award(client, app, default_club, staff_user):
    with app.app_context():
        role1 = MeetingRole(name="Role A", club_id=default_club.id, type='standard', needs_approval=False, has_single_owner=True)
        role2 = MeetingRole(name="Role B", club_id=default_club.id, type='standard', needs_approval=False, has_single_owner=True)
        db.session.add_all([role1, role2])
        db.session.commit()
        role1_id = role1.id
        role2_id = role2.id

        award = Award(club_id=default_club.id, name='Old Name', category='old-cat', max_votes_per_user=1, max_winners=1)
        db.session.add(award)
        db.session.commit()
        award_id = award.id

    login_user(client, staff_user, default_club.id)

    with patch('app.settings_routes.is_authorized', return_value=True):
        payload = {
            'id': award_id,
            'name': 'New Name',
            'max_votes': 1,
            'max_winners': 2,
            'selected_role_ids': [role2_id]
        }
        response = client.post('/api/settings/awards/update', json=payload)
        assert response.status_code == 200
        res_data = response.get_json()
        assert res_data['success'] is True

        with app.app_context():
            db_award = db.session.get(Award, award_id)
            assert db_award.name == 'New Name'
            assert db_award.max_winners == 2
            assert len(db_award.role_associations) == 1
            assert db_award.role_associations[0].meeting_role_id == role2_id

def test_delete_award(client, app, default_club, staff_user):
    with app.app_context():
        award = Award(club_id=default_club.id, name='To Delete', category='delete-me', max_votes_per_user=1, max_winners=1)
        db.session.add(award)
        db.session.commit()
        award_id = award.id

    login_user(client, staff_user, default_club.id)

    with patch('app.settings_routes.is_authorized', return_value=True):
        response = client.post(f'/api/settings/awards/delete/{award_id}')
        assert response.status_code == 200
        res_data = response.get_json()
        assert res_data['success'] is True

        with app.app_context():
            assert db.session.get(Award, award_id) is None

def test_save_default_awards(client, app, default_club, staff_user):
    with app.app_context():
        a1 = Award(club_id=default_club.id, name='A1', category='a1', max_votes_per_user=1, max_winners=1)
        a2 = Award(club_id=default_club.id, name='A2', category='a2', max_votes_per_user=1, max_winners=1)
        db.session.add_all([a1, a2])
        db.session.commit()
        a1_id = a1.id
        a2_id = a2.id

    login_user(client, staff_user, default_club.id)

    with patch('app.settings_routes.is_authorized', return_value=True):
        payload = {
            'default_award_ids': [a1_id, a2_id]
        }
        response = client.post('/api/settings/awards/default/save', json=payload)
        assert response.status_code == 200
        res_data = response.get_json()
        assert res_data['success'] is True

        with app.app_context():
            club = db.session.get(Club, default_club.id)
            assert club.get_default_awards() == [a1_id, a2_id]
