from app import create_app, db
from app.models import Pathway

app = create_app()
with app.app_context():
    pathway = Pathway.query.filter(Pathway.name.like('%Distinguished%')).first()
    if pathway:
        print(f"Found: {pathway.name}")
    else:
        print("Not Found")
