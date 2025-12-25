
from app import create_app, db
from app.models import Presentation

app = create_app()
with app.app_context():
    print("--- Presentations ---")
    pres = Presentation.query.all()
    for p in pres:
        print(f"ID: {p.id}, Code: {p.code}, Title: '{p.title}', Series: '{p.series}'")
