
import os
from app import create_app, db
from app.models import LevelRole, SessionLog, Role, SessionType, Contact, User

app = create_app()
with app.app_context():
    print("--- ALL Level Requirements ---")
    reqs = LevelRole.query.order_by(LevelRole.level, LevelRole.type).all()
    for r in reqs:
        print(f"ID: {r.id}, Level: {r.level}, Role: '{r.role}', Type: '{r.type}', Count: {r.count_required}")

    print("\n--- Inspecting Speaker Logs (Rosalía Shi) ---")
    # Finding Rosalía Shi - based on the snapshot
    contact = Contact.query.filter(Contact.Name.like('%Rosalía%')).first()
    if contact:
        print(f"Found Contact: {contact.Name} (ID: {contact.id})")
        logs = SessionLog.query.filter_by(Owner_ID=contact.id).order_by(SessionLog.Meeting_Number.desc()).all()
        for l in logs:
            actual_role_name = (l.session_type.role.name if l.session_type and l.session_type.role else (l.session_type.Title if l.session_type else "N/A"))
            print(f"ID: {l.id}, Mtg: {l.Meeting_Number}, Title: '{l.Session_Title}', Role: '{actual_role_name}', PathLevel: '{l.current_path_level}', Status: '{l.Status}'")
    else:
        print("Contact 'Rosalía' not found.")
