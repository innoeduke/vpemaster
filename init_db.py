from app import create_app, db
import os

app = create_app()
with app.app_context():
    from app import models
    print("Creating all tables...")
    db.create_all()
    print("Done.")
