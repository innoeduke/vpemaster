from app import create_app, db
from app.models import Contact, ContactClub

app = create_app()
with app.app_context():
    guests = Contact.query.filter_by(Type='Guest').all()
    guest_ids = [g.id for g in guests]
    
    ccs = ContactClub.query.filter(ContactClub.contact_id.in_(guest_ids)).all()
    
    stats = {}
    for cc in ccs:
        mtype = cc.membership_type or "None"
        stats[mtype] = stats.get(mtype, 0) + 1
        
    print(f"Total Guest Contacts: {len(guests)}")
    print(f"Club Membership Types for Guests: {stats}")
