
from app import create_app, db
from app.models import Achievement

app = create_app()

def backfill_achievements():
    """
    Iterates through all existing level-completion achievements and 
    auto-adds missing lower-level achievements.
    """
    with app.app_context():
        print("Starting backfill of missing lower-level achievements...")
        
        # Get all level completion achievements that are level 2 or higher
        # optimization: filter directly in query
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
                    print(f"Adding missing Level {i} for contact {contact_id} (Path: {path_name}) based on Level {current_level}...")
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
            db.session.commit()
            print(f"Successfully added {added_count} missing achievements.")
        else:
            print("No missing lower-level achievements found.")

if __name__ == "__main__":
    backfill_achievements()
