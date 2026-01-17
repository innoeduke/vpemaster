from app import create_app, db
from app.models.contact_club import ContactClub
from app.models.user import User
from app.models.contact import Contact

app = create_app()
with app.app_context():
    # Find ContactClubs where the contact is NOT linked to any User
    # Join ContactClub -> Contact
    # Check if Contact is linked to User
    
    # Get all users with contacts
    users_with_contacts = db.session.query(User.contact_id).filter(User.contact_id.isnot(None)).all()
    user_contact_ids = set([u[0] for u in users_with_contacts])
    
    orphans = 0
    total = 0
    
    # Iterate all ContactClubs
    for cc in ContactClub.query.all():
        total += 1
        if cc.contact_id not in user_contact_ids:
            orphans += 1
            print(f"Orphan ContactClub: Contact ID {cc.contact_id}, Club ID {cc.club_id}, Type {cc.membership_type}")

    print(f"Total ContactClubs: {total}")
    print(f"Orphaned ContactClubs (No User): {orphans}")
