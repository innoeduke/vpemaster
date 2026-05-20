import re
from datetime import date
from app import create_app, db
from app.models import Contact, Pathway, ContactPath, Achievement

def migrate_data():
    app = create_app()
    with app.app_context():
        print("Starting data migration for contact pathways...")
        
        # Load all pathways for reference
        pathways = Pathway.query.all()
        pathway_by_name = {p.name.strip().lower(): p for p in pathways if p.name}
        pathway_by_abbr = {p.abbr.strip().upper(): p for p in pathways if p.abbr}
        
        contacts = Contact.query.all()
        migrated_count = 0
        
        for contact in contacts:
            # Check legacy values from the database columns
            # (Note: we renamed columns to _Current_Path and _Completed_Paths in SQLAlchemy)
            legacy_current = contact._Current_Path
            legacy_completed = contact._Completed_Paths
            
            if not legacy_current and not legacy_completed:
                continue
                
            print(f"\nProcessing Contact: {contact.Name} (ID: {contact.id})")
            
            # Retrieve achievements for this contact's user
            uid = contact.user_id
            achievements = []
            if uid:
                achievements = Achievement.query.filter_by(user_id=uid).all()
            
            registered_pathway_ids = set()
            
            # 1. Migrate completed paths
            if legacy_completed:
                parts = [p.strip() for p in legacy_completed.split('/') if p.strip()]
                for part in parts:
                    # e.g., "PM5" or "DL" or "Dynamic Leadership"
                    match = re.match(r"^([A-Z]+)\d*$", part.upper())
                    abbr = match.group(1) if match else part
                    
                    pathway = pathway_by_abbr.get(abbr.upper()) or pathway_by_name.get(part.lower())
                    if pathway:
                        if pathway.id in registered_pathway_ids:
                            continue
                            
                        # Find completed date from achievements
                        completed_date = None
                        # Check path completion achievement
                        path_ach = next((a for a in achievements if a.achievement_type == 'path-completion' and a.path_name == pathway.name), None)
                        if path_ach:
                            completed_date = path_ach.issue_date
                        else:
                            # Fallback: check level 5 completion achievement
                            lvl5_ach = next((a for a in achievements if a.achievement_type == 'level-completion' and a.path_name == pathway.name and a.level == 5), None)
                            if lvl5_ach:
                                completed_date = lvl5_ach.issue_date
                        
                        # Create ContactPath
                        cp = ContactPath(
                            contact_id=contact.id,
                            path_id=pathway.id,
                            status='completed',
                            is_default=False,
                            registered_date=date.today(),
                            completed_date=completed_date
                        )
                        db.session.add(cp)
                        registered_pathway_ids.add(pathway.id)
                        print(f"  - Completed Path: {pathway.name} (Completed: {completed_date})")
                    else:
                        print(f"  [Warning] Pathway not found for completed code/name: {part}")
            
            # 2. Migrate current (default) path
            if legacy_current:
                pathway = pathway_by_name.get(legacy_current.strip().lower()) or pathway_by_abbr.get(legacy_current.strip().upper())
                if pathway:
                    if pathway.id in registered_pathway_ids:
                        # Already registered as completed, let's mark it as default
                        # If a contact only has completed paths, one of them could be default
                        cp = ContactPath.query.filter_by(contact_id=contact.id, path_id=pathway.id).first()
                        if cp:
                            cp.is_default = True
                            print(f"  - Set existing completed path {pathway.name} as default")
                    else:
                        # Register as working path and default
                        cp = ContactPath(
                            contact_id=contact.id,
                            path_id=pathway.id,
                            status='working',
                            is_default=True,
                            registered_date=date.today(),
                            completed_date=None
                        )
                        db.session.add(cp)
                        registered_pathway_ids.add(pathway.id)
                        print(f"  - Working Path (Default): {pathway.name}")
                else:
                    print(f"  [Warning] Pathway not found for current path: {legacy_current}")
            
            migrated_count += 1
            
        db.session.commit()
        print(f"\nSuccessfully migrated {migrated_count} contacts!")

if __name__ == '__main__':
    migrate_data()
