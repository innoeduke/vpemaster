
from app import create_app, db
from app.models import Role, Presentation, LevelRole, SessionType

def migrate():
    app = create_app()
    with app.app_context():
        print("--- Starting Data Migration ---")

        # 1. Clean up Presentation series (strip \r and whitespace)
        print("Cleaning up Presentation.series...")
        presentations = Presentation.query.all()
        for p in presentations:
            if p.series:
                original = p.series
                cleaned = p.series.strip()
                if cleaned != original:
                    p.series = cleaned
                    print(f"  Cleaned ID {p.id}: {repr(original)} -> {repr(cleaned)}")

        # 2. Correct Topicsmaster spelling in Roles
        print("Correcting Topicsmaster spelling in Role table...")
        role = Role.query.filter_by(name='Topicmaster').first()
        if role:
            role.name = 'Topicsmaster'
            print("  Updated Role ID {role.id} to 'Topicsmaster'")
        else:
            print("  'Topicmaster' role not found or already corrected.")

        # 3. Ensure Presentation requirements are in LevelRole
        print("Ensuring LevelRole presentation requirements...")
        requirements = [
            {'level': 3, 'role': 'Successful Club Series', 'type': 'required', 'count_required': 1},
            {'level': 4, 'role': 'Successful Club Series', 'type': 'required', 'count_required': 1},
            {'level': 4, 'role': 'Better Speaker Series', 'type': 'required', 'count_required': 1},
            {'level': 5, 'role': 'Successful Club Series', 'type': 'required', 'count_required': 1},
            {'level': 5, 'role': 'Leadership Excellence Series', 'type': 'required', 'count_required': 1},
        ]
        
        for req in requirements:
            existing = LevelRole.query.filter_by(
                level=req['level'], 
                role=req['role']
            ).first()
            
            if not existing:
                new_lr = LevelRole(
                    level=req['level'],
                    role=req['role'],
                    type=req['type'],
                    count_required=req['count_required']
                )
                db.session.add(new_lr)
                print(f"  Added Level {req['level']} req: {req['role']}")
            else:
                # Update type/count if they differ
                updated = False
                if existing.type != req['type']:
                    existing.type = req['type']
                    updated = True
                if existing.count_required != req['count_required']:
                    existing.count_required = req['count_required']
                    updated = True
                if updated:
                    print(f"  Updated Level {req['level']} req: {req['role']}")

        db.session.commit()
        print("--- Migration Completed Successfully ---")

if __name__ == "__main__":
    migrate()
