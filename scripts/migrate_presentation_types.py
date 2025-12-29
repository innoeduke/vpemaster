import sys
import os
from flask import Flask

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import SessionLog, SessionType, Role

app = create_app()

def migrate_presentations():
    with app.app_context():
        print("--- Migrating Presentation Data ---")
        
        # 1. Get Target Types (Destination)
        pathway_speech_type = SessionType.query.filter_by(Title='Pathway Speech').first()
        prepared_speaker_role = Role.query.filter_by(name='Prepared Speaker').first()
        
        if not pathway_speech_type:
            print("CRITICAL ERROR: 'Pathway Speech' session type not found. Aborting.")
            return
        if not prepared_speaker_role:
            print("CRITICAL ERROR: 'Prepared Speaker' role not found. Aborting.")
            return
            
        print(f"Target SessionType: {pathway_speech_type.Title} (ID: {pathway_speech_type.id})")
        print(f"Target Role: {prepared_speaker_role.name} (ID: {prepared_speaker_role.id})")
        
        # 2. Get Source Types (To be migrated)
        presentation_type = SessionType.query.filter_by(Title='Presentation').first()
        presenter_role = Role.query.filter_by(name='Presenter').first()
        
        # 3. Migrate Session Logs (Session Type)
        if presentation_type:
            logs_to_migrate = SessionLog.query.filter_by(Type_ID=presentation_type.id).all()
            print(f"Found {len(logs_to_migrate)} logs with 'Presentation' session type.")
            
            for log in logs_to_migrate:
                log.Type_ID = pathway_speech_type.id
                # Ensure the role matches the new session type's default role if currently mismatch?
                # Actually, we should just migrate the role if it's "Presenter".
            
            # Flush changes before deleting the type
            db.session.commit()
            print("Migrated logs to 'Pathway Speech'.")
        else:
            print("'Presentation' session type not found or already deleted.")

        # 4. Migrate Session Logs (Role) - independent check in case some logs use Presenter with other types
        # But specifically we want to match logs that might have used Presenter role.
        # Check by Role ID if we can find the role.
        if presenter_role:
            # We can't directly query SessionLog by role_id usually, because role is linked via SessionType...
            # Wait, SessionLog doesn't have a direct Role_ID column usually, it implies role via SessionType.
            # However, `SessionType` has `role_id`.
            # If we change `Session_Type_ID` to `Pathway Speech`, the role implicitly changes to `Prepared Speaker`
            # because `Pathway Speech` is linked to `Prepared Speaker`.
            # So step 3 actually handles the role migration for standard logs.
            
            # But we might have other SessionTypes that use 'Presenter' role? 
            # Let's check if any OTHER session type uses 'Presenter'.
            other_types = SessionType.query.filter(SessionType.role_id == presenter_role.id, SessionType.id != (presentation_type.id if presentation_type else -1)).all()
            if other_types:
                print(f"WARNING: Other session types using 'Presenter' role: {[t.Title for t in other_types]}")
                # We probably want to update these session types to use Prepared Speaker too?
                for st in other_types:
                    st.role_id = prepared_speaker_role.id
                    print(f"Updated SessionType '{st.Title}' to use 'Prepared Speaker' role.")
            
            # Now we can safely delete the role object?
            # We need to check if there are any other dependencies.
            # Like LevelRole?
            
        # 5. Delete Obsolete Types
        if presentation_type:
            db.session.delete(presentation_type)
            print("Deleted 'Presentation' session type.")
            
        if presenter_role:
             # Check if anyone is still using it (should be none after step 3 & 4)
             # But let's check LevelRole
             from app.models import LevelRole
             lrs = LevelRole.query.filter_by(role=presenter_role.name).all()
             for lr in lrs:
                 lr.role = prepared_speaker_role.name
                 print(f"Updated LevelRole (Role: {presenter_role.name}) to {prepared_speaker_role.name}.")

             db.session.delete(presenter_role)
             print("Deleted 'Presenter' role.")

        db.session.commit()
        print("Migration Complete.")

if __name__ == "__main__":
    migrate_presentations()
