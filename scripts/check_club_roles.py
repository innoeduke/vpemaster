import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import MeetingRole
from app.constants import GLOBAL_CLUB_ID
from sqlalchemy import func

from app.models import MeetingRole, Club
from app.constants import GLOBAL_CLUB_ID
from sqlalchemy import func

def check_club_roles():
    app = create_app()
    with app.app_context():
        clubs = Club.query.all()
        print(f"Scanning {len(clubs)} clubs for local standard roles...")
        
        global_roles = MeetingRole.query.filter_by(club_id=GLOBAL_CLUB_ID).all()
        global_map = {r.name: r for r in global_roles}
        
        for club in clubs:
            if club.id == GLOBAL_CLUB_ID: continue
            
            # Local roles
            local_roles = MeetingRole.query.filter_by(club_id=club.id).all()
            standard_locals = [r for r in local_roles if r.type == 'standard']
            
            if standard_locals:
                print(f"\n[Club {club.id}] '{club.club_name}': Found {len(standard_locals)} local 'standard' roles.")
                for r in standard_locals:
                     print(f" - ID: {r.id}, Name: '{r.name}'")

if __name__ == "__main__":
    check_club_roles()
