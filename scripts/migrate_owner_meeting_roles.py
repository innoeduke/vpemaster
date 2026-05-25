import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import date
from app import create_app, db
from app.models import OwnerMeetingRoles, ContactPath, Contact

def migrate_owner_roles():
    from flask import current_app
    from contextlib import nullcontext
    ctx = nullcontext() if current_app else create_app().app_context()
    with ctx:
        print("Starting back-fill of target_pathway and target_level for owner_meeting_roles...")
        
        omrs = OwnerMeetingRoles.query.filter(
            db.or_(
                OwnerMeetingRoles.target_pathway.is_(None),
                OwnerMeetingRoles.target_level.is_(None)
            )
        ).all()
        
        updated_count = 0
        
        for omr in omrs:
            contact = omr.contact
            meeting = omr.meeting
            
            # Skip guests or records with no contact
            if not contact or contact.Type == 'Guest':
                continue
                
            meeting_date = meeting.Meeting_Date if meeting and meeting.Meeting_Date else date.today()
            
            # 1. Resolve target_pathway
            resolved_pathway = None
            
            # 1a. Check associated session log's pathway
            if omr.session_log and omr.session_log.pathway:
                resolved_pathway = omr.session_log.pathway
                
            # 1b. Check contact's active pathways at the time of the meeting
            if not resolved_pathway:
                active_paths = [
                    cp for cp in contact.registered_paths
                    if cp.registered_date and cp.registered_date <= meeting_date
                    and (not cp.completed_date or cp.completed_date >= meeting_date)
                ]
                if active_paths:
                    default_cp = next((cp for cp in active_paths if cp.is_default), active_paths[0])
                    if default_cp.pathway:
                        resolved_pathway = default_cp.pathway.name
                        
            # 1c. Fallback to Contact's Current_Path
            if not resolved_pathway:
                resolved_pathway = contact.Current_Path
                
            if not resolved_pathway:
                continue
                
            # 2. Resolve target_level
            resolved_level = str(contact.get_active_level_at_date(resolved_pathway, meeting_date))
            
            # 3. Apply updates
            modified = False
            if not omr.target_pathway:
                omr.target_pathway = resolved_pathway
                modified = True
            if not omr.target_level:
                omr.target_level = resolved_level
                modified = True
                
            if modified:
                updated_count += 1
                print(f"  - Updated OMR (ID: {omr.id}) for {contact.Name} at meeting on {meeting_date}: {resolved_pathway} L{resolved_level}")
                
        db.session.commit()
        print(f"\nSuccessfully back-filled {updated_count} owner_meeting_roles records!")

if __name__ == '__main__':
    migrate_owner_roles()
