"""
Pytest configuration and fixtures.
"""
import sys
import os
import pytest

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/..'))


@pytest.fixture(scope='session')
def app():
    """Create application for testing."""
    from app import create_app
    app = create_app('config.Config')
    return app


@pytest.fixture(scope='function')
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture(scope='function')
def default_club(app):
    """Get or create a default club for testing."""
    from app.models import db, Club
    
    with app.app_context():
        club = Club.query.first()
        if not club:
            # Create a test club if none exists
            club = Club(
                club_no='000000',
                club_name='Test Club',
                district='Test District',
                division='Test Division',
                area='Test Area'
            )
            db.session.add(club)
            db.session.commit()
        return club
