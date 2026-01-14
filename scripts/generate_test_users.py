import sys
import os
from werkzeug.security import generate_password_hash

# Add parent directory to path to import app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Contact

app = create_app()

def generate_test_users():
    with app.app_context():
        print("Generating Test Users and Contacts...")
        
        num_users = 5
        base_username = "testuser"
        base_email = "test.user"
        
        for i in range(1, num_users + 1):
            username = f"{base_username}{i}"
            email = f"{base_email}.{i}@example.com"
            contact_name = f"Test Keynote Contact {i}"
            
            # Check if user already exists
            if User.query.filter_by(Username=username).first():
                print(f"User {username} already exists. Skipping.")
                continue
                
            print(f"Creating {username}...")
            
            # 1. Create Contact
            contact = Contact(
                Name=contact_name,
                Email=email,
                Type='Member',
                Club='Test Club',
                Completed_Paths='',
                Member_ID=f"TEST{i:04d}"
            )
            db.session.add(contact)
            db.session.flush() # Need ID for User
            
            # 2. Create User linked to Contact
            user = User(
                Username=username,
                Email=email,
                Pass_Hash=generate_password_hash('password', method='pbkdf2:sha256'),
                Role='Member',
                Status='active',
                Contact_ID=contact.id
            )
            db.session.add(user)
            
        db.session.commit()
        print(f"Successfully generated/verified {num_users} test users and contacts.")

if __name__ == "__main__":
    generate_test_users()
