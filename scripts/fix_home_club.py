import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.user_club import UserClub
from sqlalchemy import func

def fix_home_clubs():
    app = create_app()
    with app.app_context():
        print("Checking for users with multiple home clubs...")
        
        # Find users with multiple home clubs
        subquery = db.session.query(
            UserClub.user_id,
            func.count(UserClub.club_id).label('home_count')
        ).filter(
            UserClub.is_home == True
        ).group_by(
            UserClub.user_id
        ).having(
            func.count(UserClub.club_id) > 1
        ).all()
        
        if not subquery:
            print("✅ No users with multiple home clubs found.")
            return

        print(f"Found {len(subquery)} user(s) with multiple home clubs. Fixing...")
        
        for user_id, count in subquery:
            print(f"  - User ID {user_id} has {count} home clubs.")
            
            # Get all home club records for this user, ordered by updated_at desc (keep most recent)
            # If updated_at is same or null, falling back to ID desc
            ucs = UserClub.query.filter_by(
                user_id=user_id, 
                is_home=True
            ).order_by(
                UserClub.updated_at.desc(), 
                UserClub.id.desc()
            ).all()
            
            # Keep the first one, unset the rest
            keep_uc = ucs[0]
            print(f"    - Keeping Club ID {keep_uc.club_id} as home.")
            
            for remove_uc in ucs[1:]:
                print(f"    - Removing Club ID {remove_uc.club_id} from home.")
                remove_uc.is_home = False
                remove_uc.is_home = False
                
        # NEW LOGIC: Ensure users with strictly one club have it as home
        print("Checking for users with exactly one club but no home set...")
        
        # Get users with exactly 1 club
        single_club_users = db.session.query(
            UserClub.user_id
        ).group_by(
            UserClub.user_id
        ).having(
            func.count(UserClub.club_id) == 1
        ).all()
        
        fixed_count = 0
        for (user_id,) in single_club_users:
            uc = UserClub.query.filter_by(user_id=user_id).first()
            if uc and not uc.is_home:
                print(f"  - User {user_id} has one club ({uc.club_id}) but is_home=False. Fixing.")
                uc.is_home = True
                fixed_count += 1
                
        if fixed_count == 0:
            print("✅ All single-club users already have home set.")
        else:
            print(f"✅ Fixed {fixed_count} single-club users.")

        db.session.commit()
        print("✅ Fix complete.")

if __name__ == "__main__":
    fix_home_clubs()
