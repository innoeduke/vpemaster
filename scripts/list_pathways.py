import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Pathway

app = create_app()

with app.app_context():
    pathways = Pathway.query.all()
    print("--- Pathways ---")
    for p in pathways:
        print(f"ID: {p.id}, Name: '{p.name}', Type: '{p.type}'")
