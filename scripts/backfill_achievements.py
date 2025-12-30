import sys
import os
import argparse

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Achievement

app = create_app()

def backfill_achievements(apply=False):
    """
    Iterates through all existing level-completion achievements and 
    auto-adds missing lower-level achievements.
    """
    with app.app_context():
        if apply:
            print("Starting backfill of missing lower-level achievements (APPLY MODE)...")
        else:
            print("Starting backfill of missing lower-level achievements (DRY RUN)...")
        
        # Get all level completion achievements that are level 2 or higher
        all_achievements = Achievement.query.filter(
            Achievement.achievement_type == 'level-completion',
            Achievement.level > 1
        ).all()
        
        added_count = 0
        
        for ach in all_achievements:
            contact_id = ach.contact_id
            path_name = ach.path_name
            current_level = ach.level
            
            if not current_level:
                continue
                
            # Check for levels 1 to current_level - 1
            for i in range(1, current_level):
                exists = Achievement.query.filter_by(
                    contact_id=contact_id,
                    achievement_type='level-completion',
                    path_name=path_name,
                    level=i
                ).first()
                
                if not exists:
                    print(f"[{'WILL ADD' if not apply else 'ADDING'}] Missing Level {i} for contact {contact_id} (Path: {path_name}) based on Level {current_level}...")
                    new_ach = Achievement(
                        contact_id=contact_id,
                        member_id=ach.member_id,
                        issue_date=ach.issue_date, # Use the date of the higher level achievement
                        achievement_type='level-completion',
                        path_name=path_name,
                        level=i,
                        notes=f"Backfilled: Auto-added based on existing Level {current_level} completion"
                    )
                    db.session.add(new_ach)
                    added_count += 1
        
        if added_count > 0:
            if apply:
                db.session.commit()
                print(f"Successfully added {added_count} missing achievements.")
            else:
                print(f"DRY RUN COMPLETE: Would have added {added_count} missing achievements. Run with --apply to commit changes.")
        else:
            print("No missing lower-level achievements found.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill missing lower-level achievements.")
    parser.add_argument("--apply", action="store_true", help="Apply changes to the database.")
    args = parser.parse_args()
    
    backfill_achievements(apply=args.apply)
