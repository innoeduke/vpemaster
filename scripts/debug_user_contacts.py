from app import create_app, db
from app.models.user import User

app = create_app()

def test_user_contacts():
    with app.app_context():
        try:
            print("Fetching users...")
            users = User.query.all()
            print(f"Found {len(users)} users.")
            
            for u in users:
                print(f"Checking user {u.id} - {u.username}")
                try:
                    c = u.contact
                    print(f"  Contact: {c}")
                    if c:
                        print(f"  Contact Name: {c.Name}")
                    print(f"  Email: {u.email}")
                except Exception as e:
                    print(f"  ERROR accessing contact for user {u.id}: {e}")
                    import traceback
                    traceback.print_exc()
                    
        except Exception as e:
            print(f"General Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_user_contacts()
