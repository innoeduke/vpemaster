
from app import create_app, db
from app.models import LevelRole

app = create_app()
with app.app_context():
    requirements = [
        # Level 3
        {'level': 3, 'role': 'Successful Club Series', 'type': 'required', 'count_required': 1},
        
        # Level 4
        {'level': 4, 'role': 'Successful Club Series', 'type': 'required', 'count_required': 1},
        {'level': 4, 'role': 'Better Speaker Series', 'type': 'required', 'count_required': 1},
        
        # Level 5
        {'level': 5, 'role': 'Successful Club Series', 'type': 'required', 'count_required': 1},
        {'level': 5, 'role': 'Leadership Excellence Series', 'type': 'required', 'count_required': 1},
    ]
    
    for req in requirements:
        # Check if already exists to avoid duplicates
        existing = LevelRole.query.filter_by(
            level=req['level'], 
            role=req['role'],
            type=req['type']
        ).first()
        
        if not existing:
            new_lr = LevelRole(
                level=req['level'],
                role=req['role'],
                type=req['type'],
                count_required=req['count_required']
            )
            db.session.add(new_lr)
            print(f"Added Level {req['level']} req: {req['role']}")
        else:
            print(f"Level {req['level']} req already exists: {req['role']}")
            
    db.session.commit()
    print("Database update complete.")
