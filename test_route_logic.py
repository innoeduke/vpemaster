from app import create_app, db
from app.models import Roster, Contact, Meeting, Ticket
from app.utils import get_meeting_roles
from sqlalchemy.orm import joinedload

app = create_app()
with app.app_context():
    selected_meeting_num = 959
    club_id = 1
    
    # Simulate tools_routes.py logic
    roster_entries = Roster.query\
        .options(joinedload(Roster.roles), joinedload(Roster.ticket))\
        .outerjoin(Contact, Roster.contact_id == Contact.id)\
        .filter(Roster.meeting_number == selected_meeting_num)\
        .order_by(Roster.order_number.asc())\
        .all()
    
    roles_map = get_meeting_roles(club_id, selected_meeting_num)
    
    print(f"Roles Map Keys: {list(roles_map.keys())}")
    
    for entry in roster_entries:
        entry.booked_roles = roles_map.get(str(entry.contact_id), [])
        
        name = entry.contact.Name if entry.contact else "N/A"
        print(f"Entry {entry.id} ({name}): booked_roles={entry.booked_roles}")
