from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import current_user
from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions, permission_required
from .models import Roster, Meeting, Contact, ContactClub, Pathway, Ticket
from .club_context import get_current_club_id, authorized_club_required
from . import db
from sqlalchemy import distinct
from .utils import get_meetings_by_status
from .services.role_service import RoleService
from .constants import RoleID

roster_bp = Blueprint('roster_bp', __name__)


@roster_bp.route('/', methods=['GET'])
@login_required
@authorized_club_required
def roster():
    """Independent roster page"""
    if not is_authorized(Permissions.ROSTER_VIEW):
        return redirect(url_for('agenda_bp.agenda'))

    club_id = get_current_club_id()
    
    is_guest = not current_user.is_authenticated or \
               (hasattr(current_user, 'primary_role_name') and current_user.primary_role_name == 'Guest')
    limit_past = 8 if is_guest else None
    
    all_meetings, default_meeting_id = get_meetings_by_status(
        limit_past=limit_past, 
        columns=[Meeting.id, Meeting.Meeting_Date, Meeting.status, Meeting.Meeting_Number]
    )
    meeting_ids = [m[0] for m in all_meetings]

    selected_meeting_id_str = request.args.get('meeting_id')
    
    if selected_meeting_id_str:
        try:
            selected_meeting_id = int(selected_meeting_id_str)
        except ValueError:
            selected_meeting_id = None
    else:
        selected_meeting_id = default_meeting_id
        if not selected_meeting_id and meeting_ids:
            selected_meeting_id = meeting_ids[0]

    # Get all contacts for the dropdown menu, filtered by club
    contacts = Contact.query.join(ContactClub).filter(ContactClub.club_id == club_id)\
        .order_by(Contact.Name).all()
    Contact.populate_users(contacts, club_id)

    selected_meeting = None
    roster_entries = []
    roles_map = {}
    next_unallocated_entry = None
    
    if selected_meeting_id:
        selected_meeting = Meeting.query.get(selected_meeting_id)
        if selected_meeting and (club_id and selected_meeting.club_id != club_id):
             selected_meeting = None
 
        if selected_meeting:
            # Get roster entries for this meeting (including unallocated entries)
            roster_entries = Roster.query\
                .options(db.joinedload(Roster.roles), db.joinedload(Roster.ticket))\
                .outerjoin(Contact, Roster.contact_id == Contact.id)\
                .filter(Roster.meeting_id == selected_meeting_id)\
                .order_by(Roster.order_number.asc())\
                .all()
        
        # Auto-sync officers to roster
        club_officers = [c for c in contacts if c.user and c.user.has_role(Permissions.STAFF)]
        roster_contact_ids = {r.contact_id for r in roster_entries if r.contact_id}
        missing_officers = [o for o in club_officers if o.id not in roster_contact_ids]
        
        if missing_officers:
            officer_ticket = Ticket.get_by_name('Officer', club_id)
            officer_orders = [r.order_number for r in roster_entries if r.order_number and r.order_number >= 1000]
            next_off_order = max(officer_orders) + 1 if officer_orders else 1000
            
            for off in missing_officers:
                new_off_entry = Roster(
                    meeting_id=selected_meeting_id,
                    contact_id=off.id,
                    contact_type='Officer',
                    order_number=next_off_order,
                    ticket_id=officer_ticket.id if officer_ticket else None
                )
                db.session.add(new_off_entry)
                next_off_order += 1
            
            try:
                db.session.commit()
                # Re-fetch roster entries
                roster_entries = Roster.query\
                    .options(db.joinedload(Roster.roles), db.joinedload(Roster.ticket))\
                    .outerjoin(Contact, Roster.contact_id == Contact.id)\
                    .filter(Roster.meeting_id == selected_meeting_id)\
                    .order_by(Roster.order_number.asc())\
                    .all()
            except Exception as e:
                db.session.rollback()
                print(f"Error syncing officers: {e}")

        # Roles map
        roles_map = RoleService.get_role_takers(selected_meeting_id, club_id)
                
        
        # Calculate total amount
        total_amount = sum(entry.ticket.price for entry in roster_entries if entry.ticket and entry.ticket.price)

        if roster_entries:
            valid_orders = [entry.order_number for entry in roster_entries if entry.order_number is not None and entry.order_number < 1000]
            max_order = max(valid_orders) if valid_orders else 0
            next_unallocated_entry = type('obj', (object,), {'order_number': max_order + 1})()
        else:
            next_unallocated_entry = type('obj', (object,), {'order_number': 1})()

    pathways = {}
    all_pathways = Pathway.query.filter_by(status='active').order_by(Pathway.name).all()
    for p in all_pathways:
        ptype = p.type or "Other"
        if ptype not in pathways:
            pathways[ptype] = []
        pathways[ptype].append(p.name)

    tickets = Ticket.get_all_for_club(club_id)
    tickets_map = {t.name: t for t in tickets}

    return render_template(
        'roster.html',
        all_meetings=all_meetings,
        selected_meeting_id=selected_meeting_id,
        selected_meeting=selected_meeting,
        roles_map=roles_map,
        roster_entries=roster_entries,
        contacts=contacts,
        next_unallocated_entry=next_unallocated_entry,
        pathways=pathways,
        tickets=tickets,
        tickets_map=tickets_map,
        RoleID=RoleID,
        total_amount=total_amount if 'total_amount' in locals() else 0
    )


@roster_bp.route('/participation-trend', methods=['GET'])
@login_required
@authorized_club_required
def roster_participation_trend():
    """Stacked bar chart showing participation trend by ticket type over meetings."""
    from sqlalchemy import func
    
    club_id = get_current_club_id()
    
    all_tickets = Ticket.get_all_for_club(club_id)
    
    query = Meeting.query.filter(Meeting.status == 'finished', Meeting.Meeting_Number >= 951)
    if club_id:
        query = query.filter(Meeting.club_id == club_id)
    meetings = query.order_by(Meeting.Meeting_Number.asc()).all()
    meeting_numbers = [m.Meeting_Number for m in meetings]
    meeting_dates = [m.Meeting_Date.strftime('%Y-%m-%d') if m.Meeting_Date else '' for m in meetings]
    
    counts_query = db.session.query(
        Meeting.Meeting_Number,
        Ticket.name,
        func.count(Roster.id).label('count')
    ).join(Meeting, Roster.meeting_id == Meeting.id)\
     .join(Ticket, Roster.ticket_id == Ticket.id)\
     .filter(
        Meeting.Meeting_Number.in_(meeting_numbers),
        Ticket.name != 'Cancelled'
    ).group_by(
        Meeting.Meeting_Number,
        Ticket.name
    ).all()
    
    counts_by_meeting = {}
    for mtg_num, ticket_name, count in counts_query:
        if mtg_num not in counts_by_meeting:
            counts_by_meeting[mtg_num] = {}
        counts_by_meeting[mtg_num][ticket_name] = count
    
    datasets = []
    # Deduplicate tickets by name for the legend/labels
    # Use the first encountered ticket for styling (color/icon)
    unique_tickets = {}
    for t in all_tickets:
        if t.name not in unique_tickets:
            unique_tickets[t.name] = t

    for name, ticket in unique_tickets.items():
        if name == 'Cancelled':
            continue
        
        data = []
        for mtg_num in meeting_numbers:
            count = counts_by_meeting.get(mtg_num, {}).get(name, 0)
            data.append(count)
        
        if sum(data) > 0:
            datasets.append({
                'label': name,
                'data': data,
                'color': ticket.color or '#6c757d',
                'icon': ticket.icon or 'fa-ticket-alt'
            })
    
    return render_template('roster_participation_trend.html',
                           meeting_numbers=meeting_numbers,
                           meeting_dates=meeting_dates,
                           datasets=datasets)


@roster_bp.route('/amount-trend', methods=['GET'])
@login_required
@authorized_club_required
def roster_amount_trend():
    """Stacked bar chart showing amount trend by contact type over meetings."""
    from sqlalchemy import func
    
    club_id = get_current_club_id()
    
    query = Meeting.query.filter(Meeting.status == 'finished', Meeting.Meeting_Number >= 951)
    if club_id:
        query = query.filter(Meeting.club_id == club_id)
    meetings = query.order_by(Meeting.Meeting_Number.asc()).all()
    meeting_numbers = [m.Meeting_Number for m in meetings]
    meeting_dates = [m.Meeting_Date.strftime('%Y-%m-%d') if m.Meeting_Date else '' for m in meetings]
    
    amounts_query = db.session.query(
        Meeting.Meeting_Number,
        Roster.contact_type,
        func.sum(Roster.amount).label('total_amount')
    ).join(Meeting, Roster.meeting_id == Meeting.id)\
     .join(Ticket, Roster.ticket_id == Ticket.id)\
     .filter(
        Meeting.Meeting_Number.in_(meeting_numbers),
        Ticket.name != 'Cancelled'
    ).group_by(
        Meeting.Meeting_Number,
        Roster.contact_type
    ).all()
    
    amounts_by_meeting = {}
    for mtg_num, c_type, total in amounts_query:
        if mtg_num not in amounts_by_meeting:
            amounts_by_meeting[mtg_num] = {}
        # Ensure default to 'Guest' if contact_type is empty
        c_type = c_type or 'Guest'
        amounts_by_meeting[mtg_num][c_type] = amounts_by_meeting[mtg_num].get(c_type, 0) + (total or 0)
    
    # Define contact types and their colors
    contact_types = [
        {'name': 'Guest', 'color': '#20c997'}, # Teal
        {'name': 'Member', 'color': '#ffc107'}, # Yellow
        {'name': 'Officer', 'color': '#fd7e14'} # Orange
    ]
    
    datasets = []
    for c_type_info in contact_types:
        name = c_type_info['name']
        data = []
        for mtg_num in meeting_numbers:
            amount = amounts_by_meeting.get(mtg_num, {}).get(name, 0)
            data.append(float(amount))
            
        if sum(data) > 0:
            datasets.append({
                'label': name,
                'data': data,
                'color': c_type_info['color']
            })
            
    return render_template('roster_amount_trend.html',
                           meeting_numbers=meeting_numbers,
                           meeting_dates=meeting_dates,
                           datasets=datasets)


@roster_bp.route('/api/entry', methods=['POST'])
@login_required
@authorized_club_required
@permission_required(Permissions.ROSTER_EDIT)
def create_roster_entry():
    """Create a new roster entry"""
    data = request.get_json()

    required_fields = ['meeting_id', 'order_number', 'ticket_id']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    ticket_id = data['ticket_id']
    ticket_obj = db.session.get(Ticket, ticket_id)
    if not ticket_obj:
         return jsonify({'error': f'Invalid ticket id: {ticket_id}'}), 400

    new_entry = Roster(
        meeting_id=data['meeting_id'],
        order_number=data['order_number'],
        ticket_id=ticket_obj.id
    )

    if 'contact_id' in data and data['contact_id']:
        new_entry.contact_id = data['contact_id']

    if 'contact_type' in data:
        new_entry.contact_type = data['contact_type']

    try:
        db.session.add(new_entry)
        db.session.commit()
        return jsonify({'message': 'Entry created successfully', 'id': new_entry.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@roster_bp.route('/api/entry/<int:entry_id>', methods=['GET'])
@login_required
@authorized_club_required
def get_roster_entry(entry_id):
    entry = db.session.get(Roster, entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404
    
    contact_name = None
    contact_type = entry.contact_type

    if entry.contact:
        contact_name = entry.contact.Name
        if entry.contact.user and entry.contact.user.has_role(Permissions.STAFF):
            contact_type = 'Officer'
        elif not contact_type:
            contact_type = entry.contact.Type

    return jsonify({
        'id': entry.id,
        'meeting_number': entry.meeting_number,
        'order_number': entry.order_number,
        'ticket_id': entry.ticket_id,
        'ticket': entry.ticket.name if entry.ticket else None,
        'contact_id': entry.contact_id,
        'contact_name': contact_name,
        'contact_type': contact_type
    })


@roster_bp.route('/api/entry/<int:entry_id>', methods=['PUT'])
@login_required
@authorized_club_required
@permission_required(Permissions.ROSTER_EDIT)
def update_roster_entry(entry_id):
    entry = db.session.get(Roster, entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404

    data = request.get_json()

    if 'order_number' in data:
        entry.order_number = data['order_number']
    if 'ticket_id' in data:
        ticket_id = data['ticket_id']
        ticket_obj = db.session.get(Ticket, ticket_id)
        if ticket_obj:
            entry.ticket_id = ticket_obj.id

    if 'contact_id' in data:
        if data['contact_id']:
            entry.contact_id = data['contact_id']
        else:
            entry.contact_id = None
            
    if 'contact_type' in data:
        entry.contact_type = data['contact_type']

    try:
        db.session.commit()
        return jsonify({'message': 'Entry updated successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@roster_bp.route('/api/entry/<int:entry_id>/restore', methods=['POST'])
@login_required
@authorized_club_required
@permission_required(Permissions.ROSTER_EDIT)
def restore_roster_entry(entry_id):
    entry = db.session.get(Roster, entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404

    if entry.contact_type == 'Officer':
        ticket_name = 'Officer'
    elif entry.contact and entry.contact.Type == 'Member':
        ticket_name = 'Early-bird (Member)'
    else:
        ticket_name = 'Early-bird (Guest)'
    
    t_obj = Ticket.get_by_name(ticket_name, entry.meeting.club_id if entry.meeting else None)
    if t_obj:
        entry.ticket_id = t_obj.id

    try:
        db.session.commit()
        return jsonify({'message': 'Entry restored successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@roster_bp.route('/api/entry/<int:entry_id>', methods=['DELETE'])
@login_required
@authorized_club_required
@permission_required(Permissions.ROSTER_EDIT)
def delete_roster_entry(entry_id):
    entry = db.session.get(Roster, entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404

    hard_delete = request.args.get('hard_delete') == 'true'

    try:
        if hard_delete:
            from .models.roster import RosterRole
            RosterRole.query.filter_by(roster_id=entry_id).delete()
            db.session.delete(entry)
            message = 'Entry deleted successfully'
        else:
            cancelled_ticket = Ticket.get_by_name('Cancelled', entry.meeting.club_id if entry.meeting else None)
            if cancelled_ticket:
                entry.ticket_id = cancelled_ticket.id
            message = 'Entry cancelled successfully'
            
        db.session.commit()
        return jsonify({'message': message}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

