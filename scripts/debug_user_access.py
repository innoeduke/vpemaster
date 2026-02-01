import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, UserClub, Club

def debug_access():
    app = create_app()
    with app.app_context():
        print(f"{'User':<20} | {'Club':<20} | {'Home?':<5} | {'Level':<5}")
        print("-" * 60)
        
        users = User.query.all()
        for user in users:
            ucs = UserClub.query.filter_by(user_id=user.id).all()
            if not ucs:
                print(f"{user.username:<20} | {'NO CLUBS':<20} | {'-':<5} | {'-':<5}")
                continue
                
            for uc in ucs:
                club = Club.query.get(uc.club_id)
                club_name = club.club_name if club else f"Unknown ({uc.club_id})"
                print(f"{user.username:<20} | {club_name:<20} | {uc.is_home:<5} | {uc.club_role_level:<5}")

if __name__ == "__main__":
    debug_access()
