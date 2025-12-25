
import os
from app import create_app, db
from app.models import LevelRole, SessionLog, Role, SessionType

app = create_app()
with app.app_context():
    print("--- Level Requirements ---")
    reqs = LevelRole.query.all()
    for r in reqs:
        print(f"ID: {r.id}, Level: {r.level}, Role: '{r.role}', Type: '{r.type}', Required: {r.count_required}")

    print("\n--- Recent Session Logs (last 10) ---")
    logs = SessionLog.query.order_by(SessionLog.id.desc()).limit(20).all()
    for l in logs:
        role_name = l.session_type.role.name if l.session_type and l.session_type.role else "N/A"
        print(f"ID: {l.id}, Meeting: {l.Meeting_Number}, Title: '{l.Session_Title}', Role: '{role_name}', PathLevel: '{l.current_path_level}', Status: '{l.Status}'")
