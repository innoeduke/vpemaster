
from app import create_app, db
from app.models import Role, SessionType, SessionLog, LevelRole

app = create_app()
with app.app_context():
    print("Searching for literal 'Topicmaster' (singular) in relevant tables:")
    
    # Check SessionType Titles
    sts = SessionType.query.all()
    for s in sts:
        if 'topicmaster' == s.Title.lower():
            print(f"SessionType ID {s.id}: Title='{s.Title}'")
            
    # Check SessionLog Titles
    logs = db.session.execute(db.select(SessionLog).where(SessionLog.Session_Title.ilike('%Topicmaster%'))).scalars().all()
    for l in logs:
        print(f"SessionLog ID {l.id} (Mtg {l.Meeting_Number}): Title='{l.Session_Title}'")

    # Check Role name (it should be corrected now, but let's see if there are others)
    roles = Role.query.all()
    for r in roles:
        if 'topicmaster' == r.name.lower():
            print(f"Role ID {r.id}: Name='{r.name}'")
            
    # Check LevelRole
    lrs = LevelRole.query.all()
    for lr in lrs:
        if 'topicmaster' == lr.role.lower():
            print(f"LevelRole ID {lr.id}: Role='{lr.role}'")
