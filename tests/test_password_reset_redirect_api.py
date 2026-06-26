import pytest
from flask import url_for
from app.models import User, Club, UserClub

def test_password_reset_redirection_api(client, app, default_club):
    with app.app_context():
        from app import db
        # Create a test user
        user = User(username='reset_user', email='reset_user@example.com', status='active')
        # Setting a default password that forces reset
        user.set_password('leadership')
        db.session.add(user)
        db.session.flush()

        # Mark default_club as the home club
        uc = UserClub(user_id=user.id, club_id=default_club.id, is_home=True)
        db.session.add(uc)
        db.session.commit()

        user_id = user.id
        club_id = default_club.id

    # Post login request with the default password to trigger forced reset
    response = client.post('/login', data={
        'username': 'reset_user',
        'password': 'leadership'
    })
    # Since they used a default password, they should be redirected to auth_bp.profile with tab=password
    assert response.status_code == 302
    assert 'tab=password' in response.headers['Location']

    # Now verify that accessing a normal page (e.g. index '/') redirects them to the password profile tab
    response = client.get('/')
    assert response.status_code == 302
    assert 'tab=password' in response.headers['Location']

    # Verify that accessing the message unread count endpoint is allowed (returns 200/JSON, not redirect)
    response = client.get('/api/messages/unread-count')
    assert response.status_code == 200
    assert response.json is not None
    assert 'count' in response.json

    # Verify that accessing the message events endpoint is allowed (returns 200, not redirect)
    response = client.get('/api/messages/events')
    assert response.status_code == 200
    assert response.headers['Content-Type'].startswith('text/event-stream')

    # Verify that accessing another API endpoint (e.g. inbox messages)
    # returns 403 Forbidden with JSON instead of redirecting to the HTML page.
    response = client.get('/api/messages/inbox')
    assert response.status_code == 403
    assert response.json is not None
    assert response.json['error'] == 'Password change required'
    assert response.json['code'] == 'password_change_required'
