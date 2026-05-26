from app import create_app, db
from app.models import Permission

app = create_app()
with app.app_context():
    ref = Permission.query.filter_by(name='CONTACT_BOOK_EDIT').first()
    if ref:
        print(f"Reference: category={ref.category}, resource={ref.resource}")
        p = Permission.query.filter_by(name='CONTACT_ADD_GUEST').first()
        if not p:
            p = Permission(name='CONTACT_ADD_GUEST', category='contacts', description='Add Guest contact from roster', resource=ref.resource)
            db.session.add(p)
            db.session.commit()
            print("Added CONTACT_ADD_GUEST permission.")
        else:
            p.category = 'contacts'
            db.session.commit()
            print("Updated CONTACT_ADD_GUEST permission.")
    else:
        print("Reference permission not found.")
