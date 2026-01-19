from app import create_app, db
from app.models import User, Club, Contact, Meeting, SessionLog

app = create_app('config.Config')
with app.app_context():
    print(f"Users: {User.query.count()}")
    print(f"Clubs: {Club.query.count()}")
    print(f"Contacts: {Contact.query.count()}")
    print(f"Meetings: {Meeting.query.count()}")
    print(f"SessionLogs: {SessionLog.query.count()}")
