import pytest
from flask import url_for
from app.auth.permissions import Permissions

def test_roster_route_access(client, auth, captured_templates):
    """Test that the roster route is accessible to authorized users."""
    auth.login()
    # Assuming the test user has ROSTER_VIEW permission in the test DB setup
    response = client.get(url_for('roster_bp.roster'))
    assert response.status_code == 200
    assert any(t.name == 'roster.html' for t in captured_templates)

def test_roster_trend_route_access(client, auth, captured_templates):
    """Test that the roster participation trend route is accessible."""
    auth.login()
    response = client.get(url_for('roster_bp.roster_participation_trend'))
    assert response.status_code == 200
    assert any(t.name == 'roster_participation_trend.html' for t in captured_templates)

def test_roster_api_get_entry_not_found(client, auth):
    """Test API returning 404 for non-existent entry."""
    auth.login()
    response = client.get(url_for('roster_bp.get_roster_entry', entry_id=99999))
    assert response.status_code == 404
