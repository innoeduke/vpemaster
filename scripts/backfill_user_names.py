from app import create_app, db
from app.models import User, UserClub, Contact

def backfill_user_names(club_id=1):
    app = create_app()
    with app.app_context():
        print(f"Starting backfill for Club ID: {club_id}")
        
        # Find users in the specific club
        users_in_club = User.query.join(UserClub).filter(UserClub.club_id == club_id).all()
        
        updated_count = 0
        for user in users_in_club:
            if not user.first_name and not user.last_name:
                # Use the transient current contact if available, or fetch it
                contact = user.get_contact(club_id)
                
                if contact and (contact.first_name or contact.last_name):
                    print(f"Backfilling {user.username} from contact '{contact.Name}'")
                    # Set private fields to avoid trigger loop if any, 
                    # although setters are fine for one-time script
                    user.first_name = contact.first_name
                    user.last_name = contact.last_name
                    updated_count += 1
        
        db.session.commit()
        print(f"Backfill complete. Updated {updated_count} users.")

if __name__ == "__main__":
    import sys
    cid = 1
    if len(sys.argv) > 1:
        cid = int(sys.argv[1])
    backfill_user_names(cid)
