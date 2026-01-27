from app import create_app, db
from app.models.club import Club
app = create_app()
with app.app_context():
    c = db.session.get(Club, 1)
    if c:
        print(f'Club 1 found: {c.Name}')
    else:
        print('Club 1 NOT found')

