from app import create_app, db
from app.models import Pathway, Presentation

app = create_app()

with app.app_context():
    print("--- Pathways ---")
    pathways = Pathway.query.all()
    for p in pathways:
        print(f"Name: {p.name}, Type: {p.type}")

    print("\n--- Presentation Series ---")
    series_tuples = db.session.query(Presentation.series).distinct().all()
    series = [s[0] for s in series_tuples if s[0]]
    for s in series:
        print(f"Series: {s}")
