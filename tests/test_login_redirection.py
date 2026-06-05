import pytest
from flask import url_for
from app.models import User, Club, UserClub, AuthRole

def test_login_redirect_with_home_club(client, app, default_club):
    with app.app_context():
        from app import db
        # Create a test user
        user = User(username='has_home', email='has_home@example.com', status='active')
        user.set_password('password')
        db.session.add(user)
        db.session.flush()

        # Mark default_club as the home club
        uc = UserClub(user_id=user.id, club_id=default_club.id, is_home=True)
        db.session.add(uc)
        db.session.commit()

        user_id = user.id
        club_id = default_club.id

    # Post login request without providing a club
    response = client.post('/login', data={
        'username': 'has_home',
        'password': 'password'
    })
    # Since they have a home club, they should be redirected to main_bp.index (which resolves to '/')
    assert response.status_code == 302
    assert response.headers['Location'] == '/'

    with client.session_transaction() as sess:
        assert sess.get('current_club_id') == club_id


def test_login_redirect_without_home_club(client, app, default_club):
    with app.app_context():
        from app import db
        # Create another test user
        user = User(username='no_home', email='no_home@example.com', status='active')
        user.set_password('password')
        db.session.add(user)
        db.session.flush()

        # Link to default_club, but NOT as home club
        uc = UserClub(user_id=user.id, club_id=default_club.id, is_home=False)
        db.session.add(uc)
        db.session.commit()

        user_id = user.id

    # Post login request
    response = client.post('/login', data={
        'username': 'no_home',
        'password': 'password'
    })
    # Since they have no home club, they should be redirected to clubs_bp.list_clubs (which resolves to '/clubs')
    assert response.status_code == 302
    assert response.headers['Location'] == '/clubs'
