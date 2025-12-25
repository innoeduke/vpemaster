
from app import create_app, db
from app.models import Role, SessionType, SessionLog, LevelRole

app = create_app()
with app.app_context():
    print("--- Role Table ---")
    roles = Role.query.all()
    for r in roles:
        if 'topic' in r.name.lower():
            print(f"Role ID {r.id}: '{r.name}'")

    print("\n--- LevelRole Table ---")
    lrs = LevelRole.query.all()
    for lr in lrs:
        if 'topic' in lr.role.lower():
            print(f"Level {lr.level} Req (ID {lr.id}): '{lr.role}'")

    print("\n--- SessionLog Table (Recent matches) ---")
    # Checking SessionLog titles or derived role names
    logs = SessionLog.query.order_by(SessionLog.id.desc()).all()
    found_count = 0
    for l in logs:
        role_name = (l.session_type.role.name if l.session_type and l.session_type.role else (l.session_type.Title if l.session_type else "")).strip()
        if 'topicmaster' in role_name.lower() or 'topicmaster' in l.Session_Title.lower():
            print(f"Log ID {l.id} (Mtg {l.Meeting_Number}): Title='{l.Session_Title}', Role='{role_name}'")
            found_count += 1
            if found_count > 20: break
