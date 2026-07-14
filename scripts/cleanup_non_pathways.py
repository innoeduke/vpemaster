import os
import sys

# Ensure the script directory is in the Python path so it can import the app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import OwnerMeetingRoles
from app.utils import is_pathway_role

def clean_database():
    app = create_app()
    with app.app_context():
        print("Starting production database cleanup for non-pathway roles...")
        
        # Query all records that have a target pathway or level assigned
        records = OwnerMeetingRoles.query.filter(
            db.or_(
                OwnerMeetingRoles.target_pathway.isnot(None),
                OwnerMeetingRoles.target_level.isnot(None)
            )
        ).all()
        
        updated_count = 0
        
        for omr in records:
            is_speech_project = False
            project_id = None
            if omr.session_log:
                is_speech_project = (omr.session_log.session_type and omr.session_log.session_type.Title in ['Prepared Speech', 'Presentation', 'Keynote Speaker', 'Hot Seat Speaker'])
                project_id = omr.session_log.Project_ID
                
            is_path_role = is_pathway_role(
                role_name=omr.role.name if omr.role else (omr.session_log.session_type.Title if (omr.session_log and omr.session_log.session_type) else None),
                is_speech_project=is_speech_project,
                project_id=project_id,
                role_type=omr.role.type if omr.role else None,
                club_id=omr.role.club_id if omr.role else None
            )
            
            # If it is not a pathway role, clear the target pathway and level
            if not is_path_role:
                # Store original values for printing/logging
                old_path = omr.target_pathway
                old_level = omr.target_level
                role_display = omr.role.name if omr.role else "Unknown Role"
                
                omr.target_pathway = None
                omr.target_level = None
                updated_count += 1
                
                print(f"  [CLEANED] Record ID {omr.id:04d} (Role: {role_display}): Reset '{old_path}' (L{old_level}) -> Non Pathway")
        
        if updated_count > 0:
            db.session.commit()
            print(f"\nCleanup complete. Successfully updated {updated_count} records.")
        else:
            print("\nNo incorrect records found. Database is clean!")

if __name__ == '__main__':
    clean_database()
