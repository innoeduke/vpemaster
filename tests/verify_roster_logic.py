
from app import create_app, db
from app.models import Roster, Contact, User
from app.models.roster import Role
from sqlalchemy import func

app = create_app()

with app.app_context():
    print("starting verification...")
    # Setup Data
    meeting_num = 9999
    
    # Ensure clean state
    Roster.query.filter_by(meeting_number=meeting_num).delete()
    db.session.commit()

    # Create Contacts
    officer_contact = Contact.query.filter_by(Name="Test Officer").first()
    if not officer_contact:
        officer_contact = Contact(Name="Test Officer", Type="Officer")
        db.session.add(officer_contact)
    
    member_contact = Contact.query.filter_by(Name="Test Member").first()
    if not member_contact:
        member_contact = Contact(Name="Test Member", Type="Member")
        db.session.add(member_contact)

    guest_contact = Contact.query.filter_by(Name="Test Guest").first()
    if not guest_contact:
        guest_contact = Contact(Name="Test Guest", Type="Guest")
        db.session.add(guest_contact)
        
    role = Role.query.first()
    if not role:
        role = Role(name="Test Role", type="functionary", needs_approval=False, is_distinct=False)
        db.session.add(role)

    db.session.commit()

    print(f"Testing with Role: {role.name}")

    # Test 1: Officer Assignment
    print("Testing Officer Assignment...")
    Roster.sync_role_assignment(meeting_num, officer_contact.id, role, 'assign')
    db.session.commit()
    
    officer_entry = Roster.query.filter_by(meeting_number=meeting_num, contact_id=officer_contact.id).first()
    print(f"Officer Order: {officer_entry.order_number}")
    print(f"Officer Ticket: {officer_entry.ticket}")
    
    assert officer_entry.order_number >= 1000, "Officer should have order number >= 1000"
    assert officer_entry.ticket == "Officer", "Officer should have Officer ticket"

    # Test 2: Member Assignment
    print("Testing Member Assignment...")
    Roster.sync_role_assignment(meeting_num, member_contact.id, role, 'assign')
    db.session.commit()
    
    member_entry = Roster.query.filter_by(meeting_number=meeting_num, contact_id=member_contact.id).first()
    print(f"Member Order: {member_entry.order_number}")
    print(f"Member Ticket: {member_entry.ticket}")
    
    assert member_entry.order_number is None, "Member should have None order number"
    assert member_entry.ticket == "Member", "Member should have Member ticket"

    # Test 3: Guest Assignment
    print("Testing Guest Assignment...")
    Roster.sync_role_assignment(meeting_num, guest_contact.id, role, 'assign')
    db.session.commit()
    
    guest_entry = Roster.query.filter_by(meeting_number=meeting_num, contact_id=guest_contact.id).first()
    print(f"Guest Order: {guest_entry.order_number}")
    print(f"Guest Ticket: {guest_entry.ticket}")
    
    assert guest_entry.order_number is None, "Guest should have None order number"
    assert guest_entry.ticket == "Role Taker", "Guest should have Role Taker ticket"

    # Cleanup
    Roster.query.filter_by(meeting_number=meeting_num).delete()
    db.session.commit()
    
    print("Verification Passed!")
