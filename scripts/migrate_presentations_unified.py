import os
import sys
from sqlalchemy import func

# Add the project root to sys.path so we can import the app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Presentation, Project, Pathway, PathwayProject, SessionLog, SessionType, Role, LevelRole

def migrate_presentations_unified():
    app = create_app()
    with app.app_context():
        print("--- Unified Presentation Migration Started ---")

        # --- PART 1: Migrate Presentation Table to Project Table ---
        presentations = Presentation.query.all()
        print(f"Found {len(presentations)} entries in Presentation table to process.")

        # Get current max ID to avoid collisions
        max_id = db.session.query(func.max(Project.id)).scalar() or 0
        next_id = max_id + 1

        projects_added = 0
        pathways_linked = 0

        for p in presentations:
            # Check if project already exists (idempotency by title and format)
            existing_project = Project.query.filter_by(Project_Name=p.title, Format='Presentation').first()
            
            if not existing_project:
                print(f"  Creating project for: {p.title} (ID: {next_id})")
                new_project = Project(
                    id=next_id,
                    Project_Name=p.title,
                    Format='Presentation',
                    Duration_Min=10,
                    Duration_Max=15,
                    Introduction=f"Presentation from series: {p.series}",
                    Purpose="Educational Presentation",
                    Requirements="View resources"
                )
                db.session.add(new_project)
                project_id = next_id
                next_id += 1
                projects_added += 1
            else:
                project_id = existing_project.id

            # Link to Pathway
            if p.series:
                pathway = Pathway.query.filter_by(name=p.series).first()
                if pathway:
                    # Check if link exists
                    existing_link = PathwayProject.query.filter_by(
                        path_id=pathway.id,
                        project_id=project_id
                    ).first()
                    
                    if not existing_link:
                        print(f"    Linking to pathway: {pathway.name} (Code: {p.code}, Level: {p.level})")
                        new_link = PathwayProject(
                            path_id=pathway.id,
                            project_id=project_id,
                            code=p.code,
                            type='elective',
                            level=p.level
                        )
                        db.session.add(new_link)
                        pathways_linked += 1
                    else:
                         # Update level if missing or different
                         if existing_link.level != p.level:
                             existing_link.level = p.level
        
        db.session.commit()
        print(f"Part 1 Complete: {projects_added} projects added, {pathways_linked} links created.")

        # --- PART 2: Backfill level for ALL projects ---
        print("\nPart 2: Backfilling level data for all projects...")
        pathway_projects = PathwayProject.query.all()
        updates_count = 0
        
        for pp in pathway_projects:
            original_level = pp.level
            derived_level = None
            
            if pp.code:
                # Try parsing standard format "L.X" or "L.X.Y"
                if pp.code[0].isdigit():
                     try:
                         parts = pp.code.split('.')
                         if len(parts) >= 2:
                             derived_level = int(parts[0])
                     except ValueError:
                         pass
            
            if derived_level:
                new_level = derived_level
            else:
                # Fallback to presentation lookup
                pres = Presentation.query.filter_by(code=pp.code).first()
                if pres:
                    new_level = pres.level
                else:
                    new_level = original_level
            
            if new_level != original_level and new_level is not None:
                pp.level = new_level
                updates_count += 1
                
        db.session.commit()
        print(f"Part 2 Complete: {updates_count} level updates.")

        # --- PART 3: Migrate Session Logs and Types/Roles ---
        print("\nPart 3: Migrating Session Types and Roles...")
        
        # Get Destination Types
        pathway_speech_type = SessionType.query.filter_by(Title='Pathway Speech').first()
        prepared_speaker_role = Role.query.filter_by(name='Prepared Speaker').first()
        
        if not pathway_speech_type or not prepared_speaker_role:
             print("ERROR: 'Pathway Speech' type or 'Prepared Speaker' role missing. Skipping Part 3/4.")
        else:
            # Source Types
            legacy_presentation_type = SessionType.query.filter_by(Title='Presentation').first()
            legacy_presenter_role = Role.query.filter_by(name='Presenter').first()
            
            # Migrate Logs
            if legacy_presentation_type:
                logs_to_migrate = SessionLog.query.filter_by(Type_ID=legacy_presentation_type.id).all()
                if logs_to_migrate:
                    print(f"  Migrating {len(logs_to_migrate)} logs from 'Presentation' to 'Pathway Speech'...")
                    for log in logs_to_migrate:
                        log.Type_ID = pathway_speech_type.id
            
            # Migrate Role Usage in Other Session Types
            if legacy_presenter_role:
                other_types = SessionType.query.filter(SessionType.role_id == legacy_presenter_role.id).all()
                for st in other_types:
                    st.role_id = prepared_speaker_role.id
                    print(f"  Updated SessionType '{st.Title}' to use 'Prepared Speaker' role.")
                
                # Update LevelRole references
                lrs = LevelRole.query.filter_by(role=legacy_presenter_role.name).all()
                for lr in lrs:
                    lr.role = prepared_speaker_role.name
                    print(f"  Updated LevelRole entry for '{legacy_presenter_role.name}' to '{prepared_speaker_role.name}'.")

            # --- PART 4: Cleanup Legacy Types ---
            print("\nPart 4: Cleaning up obsolete types and roles...")
            if legacy_presentation_type:
                db.session.delete(legacy_presentation_type)
                print("  Deleted 'Presentation' session type.")
            
            if legacy_presenter_role:
                db.session.delete(legacy_presenter_role)
                print("  Deleted 'Presenter' role.")

            db.session.commit()
            print("Part 3 & 4 Complete.")

        print("\n--- Unified Migration Complete ---")

if __name__ == "__main__":
    migrate_presentations_unified()
