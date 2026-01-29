from app import create_app, db
from app.models import MeetingRole
app = create_app()
with app.app_context():
    roles = MeetingRole.query.filter(MeetingRole.name.like('%Topic%')).all()
    print("Found 'Topic' roles:")
    for r in roles:
        print(f" - {r.name}")
