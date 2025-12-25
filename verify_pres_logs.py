
from app import create_app, db
from app.models import SessionLog, SessionType, Presentation

app = create_app()
with app.app_context():
    # Find logs that are presentations
    pres_type = SessionType.query.filter_by(Title='Presentation').first()
    if pres_type:
        logs = SessionLog.query.filter_by(Type_ID=pres_type.id).all()
        print(f"Found {len(logs)} presentation logs.")
        for l in logs:
            pres = Presentation.query.get(l.Project_ID)
            owner_name = l.owner.Name if l.owner else "Unknown"
            series = pres.series if pres else "N/A"
            print(f"Log ID: {l.id}, Owner: {owner_name}, Mtg: {l.Meeting_Number}, Title: '{l.Session_Title}', Series: '{series}'")
    else:
        print("SessionType 'Presentation' not found.")
