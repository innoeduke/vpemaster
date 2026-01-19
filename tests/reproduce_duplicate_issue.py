import pytest
from app import create_app, db
from app.models import User, Club, Contact, UserClub, ContactClub
from datetime import date

@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

def test_duplicate_user_detection_by_name(app, client):
    # 1. Setup Data
    # Create Club 1 and Club 951
    club1 = Club(club_name="Club 1")
    club951 = Club(club_name="Club 951")
    db.session.add_all([club1, club951])
    db.session.commit()

    # Create User "Avril Zhang" in Club 1
    # Note: User model has _first_name, _last_name but exposed via properties
    avril = User(
        username="avril.zhang",
        email="avril@example.com",
        first_name="Avril",
        last_name="Zhang",
        created_at=date.today()
    )
    avril.set_password("password")
    db.session.add(avril)
    db.session.commit()

    # Link Avril to Club 1
    uc = UserClub(user_id=avril.id, club_id=club1.id)
    db.session.add(uc)
    
    # Create sysadmin user for login
    admin = User(username="admin", email="admin@test.com", status="active")
    admin.set_password("password")
    db.session.add(admin)
    db.session.commit()
    
    # Login as admin
    with client:
        client.post('/auth/login', data={'username': 'admin', 'password': 'password'})
        
        # 2. Simulate Check Duplicates in Club 951
        # Trigger check with ONLY Name matching (different or empty email/username input)
        # The user said "adding a user Avril Zhang", implies they typed the name.
        payload = {
            'username': 'avril.new', # Different username
            'full_name': 'Avril Zhang', # SAME Name
            'email': 'avril.new@example.com', # Different email
            'phone': '',
            'club_id': club951.id
        }
        
        response = client.post('/user/check_duplicates', json=payload)
        data = response.get_json()
        
        print(f"\nResponse Data: {data}")
        
        duplicates = data.get('duplicates', [])
        
        # 3. Assertions
        # Expect to find the existing User "Avril Zhang"
        found = any(d['type'] == 'User' and d['username'] == 'avril.zhang' for d in duplicates)
        
        if not found:
            print("\nFAILURE: Did not find existing user 'Avril Zhang' when searching by name 'Avril Zhang'")
        else:
            print("\nSUCCESS: Found existing user 'Avril Zhang'")
            
        assert found, "Should find existing user by Full Name even if email/username differs"
