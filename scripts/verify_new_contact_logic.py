from app import create_app, db
from app.models import Contact, ContactClub
from app.club_context import get_or_set_default_club

app = create_app()
with app.app_context():
    # Cleanup previous messy runs
    Contact.query.filter_by(Name="Test GuestBot").delete()
    db.session.commit()

    # Simulate logic
    first_name = "Test"
    last_name = "GuestBot"
    name = "Test GuestBot"
    contact_type = "Member" # Override logic will trigger
    
    # Simulate override in route
    is_new = True 
    if is_new:
        contact_type = 'Guest'
    
    new_contact = Contact(first_name=first_name, last_name=last_name, Name=name, Type=contact_type)
    db.session.add(new_contact)
    db.session.commit()
    
    club_id = get_or_set_default_club()
    db.session.add(ContactClub(contact_id=new_contact.id, club_id=club_id, membership_type=contact_type, is_primary=True))
    db.session.commit()
    
    # Verify
    verify_contact = Contact.query.get(new_contact.id)
    verify_cc = ContactClub.query.filter_by(contact_id=new_contact.id).first()
    
    print(f"Verified Contact Type: {verify_contact.Type}")
    print(f"Verified Club Membership: {verify_cc.membership_type}")
    
    # Final Cleanup
    db.session.delete(verify_cc)
    db.session.delete(verify_contact)
    db.session.commit()
