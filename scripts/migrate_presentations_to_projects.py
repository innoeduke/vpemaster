import os
import sys

# Standard reusable script block to handle application context
def get_app():
    # Attempt to add current directory to path if needed for local imports
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if base_dir not in sys.path:
        sys.path.append(base_dir)
        
    try:
        from app import create_app
        return create_app()
    except ImportError as e:
        print(f"Error: Could not import 'app'. Ensure this script is run from the project root or 'scripts' directory.")
        print(f"Details: {e}")
        sys.exit(1)

def migrate_presentations():
    app = get_app()
    with app.app_context():
        from app import db
        from app.models import Presentation, Project, Pathway, PathwayProject
        from sqlalchemy import func, text

        # --- Part 0: Ensure 'level' column exists ---
        # REMOVED: Managed by Flask-Migrate now.

        # --- Part 1: Migrate Presentations to Projects ---
        presentations = Presentation.query.all()
        print(f"Found {len(presentations)} presentations to process.")

        # Get current max ID
        max_id = db.session.query(func.max(Project.id)).scalar() or 0
        next_id = max_id + 1
        print(f"Starting Project ID: {next_id}")

        projects_added = 0
        pathways_linked = 0

        for p in presentations:
            # Check if project already exists (idempotency)
            existing_project = Project.query.filter_by(Project_Name=p.title, Format='Presentation').first()
            
            if not existing_project:
                print(f"Creating project for: {p.title} (ID: {next_id})")
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
                # print(f"Project already exists for: {p.title}")
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
                        print(f"  Linking to pathway: {pathway.name}")
                        new_link = PathwayProject(
                            path_id=pathway.id,
                            project_id=project_id,
                            code=p.code,
                            type='elective',
                            level=p.level # Set level directly if creating new link
                        )
                        db.session.add(new_link)
                        pathways_linked += 1
                    else:
                         # Update level if missing
                         if existing_link.level != p.level:
                             existing_link.level = p.level
                             # print(f"  Updated level to {p.level} for existing link.")

        
        # --- Part 2: Backfill Level for ALL projects ---
        print("\nBackfilling level data for all projects...")
        pathway_projects = PathwayProject.query.all()
        updates_count = 0
        
        for pp in pathway_projects:
            original_level = pp.level
            new_level = original_level
            
            # Case A: Presentations (via code match)
            # Find matching presentation by code (if applicable)
            # Note: presentation codes might overlap, but series is usually distinct.
            # We trust 'code' if it maps to a presentation.
            # But wait, standard projects also have codes like '1.1'.
            
            # Logic: 
            # 1. Try to parse standard code (e.g. "1.1")
            # 2. If valid level found, use it.
            # 3. Else look up in Presentation table.
            
            derived_level = None
            
            if pp.code:
                # Try parsing standard format "L.X" or "L.X.Y"
                if pp.code[0].isdigit():
                     try:
                         # Assumes format "Level.ProjectIndex" e.g. "1.2" -> Level 1
                         parts = pp.code.split('.')
                         if len(parts) >= 2:
                             derived_level = int(parts[0])
                     except ValueError:
                         pass
            
            if derived_level:
                new_level = derived_level
            else:
                # Fallback to presentation lookup
                # Note: Presentation code might not be unique globally, but within context...
                # Actually, presentation codes in this DB seem to be unique or specific.
                pres = Presentation.query.filter_by(code=pp.code).first()
                if pres:
                    new_level = pres.level
            
            if new_level != original_level and new_level is not None:
                pp.level = new_level
                updates_count += 1
                
        if projects_added > 0 or pathways_linked > 0 or updates_count > 0:
            db.session.commit()
            print(f"\nMigration Complete.")
            print(f"  Projects Added: {projects_added}")
            print(f"  Pathway Links Created: {pathways_linked}")
            print(f"  Level Updates: {updates_count}")
        else:
            print("\nNo changes made.")

if __name__ == "__main__":
    migrate_presentations()
