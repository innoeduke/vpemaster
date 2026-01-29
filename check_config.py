from app import create_app, db
from app.models import LevelRole, MeetingRole
from app.utils import get_role_aliases

app = create_app()
with app.app_context():
    print("--- LEVEL 1 REQUIREMENTS ---")
    reqs = LevelRole.query.filter_by(level=1).all()
    for r in reqs:
        print(f"Role: {r.role}, Type: {r.type}, Count: {r.count_required}")
        
    print("\n--- LEVEL 2 REQUIREMENTS ---")
    reqs = LevelRole.query.filter_by(level=2).all()
    for r in reqs:
        print(f"Role: {r.role}, Type: {r.type}, Count: {r.count_required}")

    print("\n--- ROLE ALIASES ---")
    aliases = get_role_aliases()
    for k, v in aliases.items():
        print(f"{k} -> {v}")
        
    print("\n--- ALL ROLES ---")
    roles = MeetingRole.query.all()
    for r in roles:
        print(r.name)

