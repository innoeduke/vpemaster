from app import create_app, db
from app.models import User, Contact, Club

app = create_app('config.Config')

with app.app_context():
    try:
        # Create user manually
        username = "sysadmin_test"
        u = User(username=username, email="test@test.com", status='active')
        u.set_password("password")
        
        db.session.add(u)
        db.session.commit()
        
        # Verify
        u_db = db.session.get(User, u.id)
        print(f"Original: {username}")
        print(f"Saved:    {u_db.username}")
        
        if u_db.username != username:
            print("FAILURE: Truncation detected!")
        else:
            print("SUCCESS: No truncation.")
            
        # Clean up
        db.session.delete(u)
        db.session.commit()
        
    except Exception as e:
        print(f"Error: {e}")
