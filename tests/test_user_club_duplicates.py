import pytest
from sqlalchemy.exc import IntegrityError
from app import create_app, db
from app.models import User, Contact, Club, UserClub
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

@pytest.fixture
def test_app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

def test_duplicate_user_club_entry(test_app):
    """
    Verify that the database prevents duplicate UserClub entries 
    for the same user_id and club_id.
    """
    with test_app.app_context():
        # Setup: Create User and Club
        club = Club(club_no='999', club_name='Test Club')
        db.session.add(club)
        
        user = User(username='testuser', email='test@example.com')
        user.set_password('password')
        db.session.add(user)
        
        db.session.commit()
        
        # 1. Add user to club first time
        # Note: We need a contact linked too, usually, but for this constraint check
        # we specifically care about user_id + club_id
        uc1 = UserClub(user_id=user.id, club_id=club.id)
        db.session.add(uc1)
        db.session.commit()
        
        # 2. Attempt to add same user to same club again
        uc2 = UserClub(user_id=user.id, club_id=club.id)
        db.session.add(uc2)
        
        # 3. Verify IntegrityError is raised
        with pytest.raises(IntegrityError):
            db.session.commit()
