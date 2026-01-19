from app import create_app, db
from app.models import User, UserClub, Contact

def clean_test_users(club_id=1, dry_run=True):
    app = create_app()
    with app.app_context():
        print(f"Checking for test users in Club ID: {club_id} (Dry Run: {dry_run})")
        
        # Find users in the specific club with null names
        users_in_club = User.query.join(UserClub).filter(
            UserClub.club_id == club_id,
            (User._first_name == None) | (User._first_name == ''),
            (User._last_name == None) | (User._last_name == '')
        ).all()
        
        if not users_in_club:
            print("No users found with null names in this club.")
            return

        print(f"Found {len(users_in_club)} users with null names:")
        for user in users_in_club:
            # Check if they belong to other clubs
            other_clubs = UserClub.query.filter(UserClub.user_id == user.id, UserClub.club_id != club_id).count()
            print(f"- {user.username} (Email: {user.email}, Other Clubs: {other_clubs})")
            
            if not dry_run:
                if other_clubs == 0:
                    # Only in this club, delete user entirely
                    # This will cascade delete UserClub records
                    print(f"  Deleting user {user.username}...")
                    db.session.delete(user)
                else:
                    # Belongs to other clubs, just remove from this club
                    print(f"  Removing {user.username} from Club {club_id}...")
                    uc = UserClub.query.filter_by(user_id=user.id, club_id=club_id).first()
                    if uc:
                        db.session.delete(uc)
        
        if not dry_run:
            db.session.commit()
            print("Cleanup complete.")
        else:
            print("Dry run finished. No changes made.")

if __name__ == "__main__":
    import sys
    dry = True
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'false':
        dry = False
    clean_test_users(1, dry_run=dry)
