from app import create_app, db
from app.models.session import SessionType
from app.models.roster import MeetingRole

app = create_app()
with app.app_context():
    print("Checking Session Types for Club 1 (Tech Support)...")
    types_1 = SessionType.get_all_for_club(1)
    print(f"Found {len(types_1)} session types.")
    for t in types_1:
        print(f" - {t.Title} (ID: {t.id}, Club: {t.club_id})")

    print("\nChecking Meeting Roles for Club 1 (Tech Support)...")
    roles_1 = MeetingRole.get_all_for_club(1)
    print(f"Found {len(roles_1)} roles.")
    for r in roles_1:
        print(f" - {r.name} (ID: {r.id}, Club: {r.club_id})")

    print("\nChecking Session Types for Club 3 (Shanghai Leadership)...")
    types_3 = SessionType.get_all_for_club(3)
    print(f"Found {len(types_3)} session types.")
    
    # Check for specific standard types
    std_types = ["Prepared Speech", "Table Topics", "Evaluation"]
    for title in std_types:
        found = any(t.Title == title for t in types_3)
        print(f" - {title}: {'FOUND' if found else 'MISSING'}")
