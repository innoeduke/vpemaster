
from app import create_app, db
from app.models import Role, SessionType, SessionLog

app = create_app()
with app.app_context():
    # Update Role names
    roles = Role.query.filter_by(name='Topicmaster').all()
    print(f"Updating {len(roles)} Role entries...")
    for r in roles:
        r.name = 'Topicsmaster'
    
    # Update SessionType titles if they match exactly
    sts = SessionType.query.filter_by(Title='Topicmaster').all()
    print(f"Updating {len(sts)} SessionType entries...")
    for s in sts:
        s.Title = 'Topicsmaster'
    
    # SessionLog role names are often derived, but let's check titles too
    # Actually, let's just make sure the Role objects are correct, as Route logic uses them.
    
    db.session.commit()
    print("Spelling correction committed.")
