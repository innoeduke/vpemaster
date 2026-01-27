
import csv
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.roster import MeetingRole
from app.models.session import SessionType
from app.constants import GLOBAL_CLUB_ID

def export_global_data():
    app = create_app()
    with app.app_context():
        # Export Meeting Roles
        roles_file = os.path.join(app.root_path, '..', 'deploy', 'meeting_roles_club_1.csv')
        print(f"Exporting Club {GLOBAL_CLUB_ID} Roles to {roles_file}...")
        
        roles = MeetingRole.query.filter_by(club_id=GLOBAL_CLUB_ID).all()
        
        if roles:
            with open(roles_file, 'w', newline='', encoding='utf-8') as f:
                # Get headers dynamically but exclude internal SA state
                headers = [c.name for c in MeetingRole.__table__.columns if c.name != 'club_id']
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for role in roles:
                    # Convert to dict
                    data = {c.name: getattr(role, c.name) for c in MeetingRole.__table__.columns if c.name != 'club_id'}
                    writer.writerow(data)
        else:
            print("No global roles found.")

        # Export Session Types
        types_file = os.path.join(app.root_path, '..', 'deploy', 'session_types_club_1.csv')
        print(f"Exporting Club {GLOBAL_CLUB_ID} Session Types to {types_file}...")
        
        types = SessionType.query.filter_by(club_id=GLOBAL_CLUB_ID).all()
        
        if types:
            with open(types_file, 'w', newline='', encoding='utf-8') as f:
                headers = [c.name for c in SessionType.__table__.columns if c.name != 'club_id']
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for st in types:
                    data = {c.name: getattr(st, c.name) for c in SessionType.__table__.columns if c.name != 'club_id'}
                    writer.writerow(data)
        else:
            print("No global session types found.")
            
        print("Export completed.")

if __name__ == "__main__":
    export_global_data()
