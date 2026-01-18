from app import create_app, db
from app.models import Contact, ContactClub

app = create_app()
with app.app_context():
    # Find all contacts of type Guest
    guests = Contact.query.filter_by(Type='Guest').all()
    guest_ids = [g.id for g in guests]
    
    if not guest_ids:
        print("No Guest contacts found.")
    else:
        # Update their membership_type in contact_clubs if it's not already 'Guest'
        updated_count = ContactClub.query.filter(
            ContactClub.contact_id.in_(guest_ids),
            ContactClub.membership_type != 'Guest'
        ).update({ContactClub.membership_type: 'Guest'}, synchronize_session=False)
        
        db.session.commit()
        print(f"Updated {updated_count} records to 'Guest' in contact_clubs.")
