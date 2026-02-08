from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import current_user
from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
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
    
    all_meetings, default_meeting_num = get_meetings_by_status(limit_past=limit_past)
    meeting_numbers = [m.Meeting_Number for m in all_meetings]

    selected_meeting_str = request.args.get('meeting_number')
    
    if selected_meeting_str:
        try:
            selected_meeting_num = int(selected_meeting_str)
        except ValueError:
            selected_meeting_num = None
    else:
        selected_meeting_num = default_meeting_num
        if not selected_meeting_num and meeting_numbers:
            selected_meeting_num = meeting_numbers[0]

    # Get all contacts for the dropdown menu, filtered by club
    contacts = Contact.query.join(ContactClub).filter(ContactClub.club_id == club_id)\
        .order_by(Contact.Name).all()
    Contact.populate_users(contacts, club_id)

    selected_meeting = None
    roster_entries = []
    roles_map = {}
    next_unallocated_entry = None
    
    if selected_meeting_num:
        query = Meeting.query.filter(Meeting.Meeting_Number == selected_meeting_num)
        if club_id:
            query = query.filter(Meeting.club_id == club_id)
        selected_meeting = query.first()

        # Get roster entries for this meeting (including unallocated entries)
        roster_entries = Roster.query\
            .options(db.joinedload(Roster.roles), db.joinedload(Roster.ticket))\
            .outerjoin(Contact, Roster.contact_id == Contact.id)\
            .filter(Roster.meeting_number == selected_meeting_num)\
            .order_by(Roster.order_number.asc())\
            .all()
        
        # Auto-sync officers to roster
        club_officers = [c for c in contacts if c.user and c.user.has_role(Permissions.STAFF)]
        roster_contact_ids = {r.contact_id for r in roster_entries if r.contact_id}
        missing_officers = [o for o in club_officers if o.id not in roster_contact_ids]
        
        if missing_officers:
            officer_ticket = Ticket.query.filter_by(name='Officer').first()
            officer_orders = [r.order_number for r in roster_entries if r.order_number and r.order_number >= 1000]
            next_off_order = max(officer_orders) + 1 if officer_orders else 1000
            
            for off in missing_officers:
                new_off_entry = Roster(
                    meeting_number=selected_meeting_num,
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
                    .filter(Roster.meeting_number == selected_meeting_num)\
                    .order_by(Roster.order_number.asc())\
                    .all()
            except Exception as e:
                db.session.rollback()
                print(f"Error syncing officers: {e}")

        roles_map = RoleService.get_role_takers(selected_meeting_num, club_id)
                
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

    tickets = Ticket.query.order_by(Ticket.id).all()
    tickets_map = {t.name: t for t in tickets}

    return render_template(
        'roster.html',
        all_meetings=all_meetings,
        selected_meeting=selected_meeting,
        selected_meeting_num=selected_meeting_num,
        roles_map=roles_map,
        roster_entries=roster_entries,
        contacts=contacts,
        meeting_numbers=meeting_numbers,
        next_unallocated_entry=next_unallocated_entry,
        pathways=pathways,
        tickets=tickets,
        tickets_map=tickets_map,
        RoleID=RoleID
    )


@roster_bp.route('/participation-trend', methods=['GET'])
@login_required
@authorized_club_required
def roster_participation_trend():
    """Stacked bar chart showing participation trend by ticket type over meetings."""
    from sqlalchemy import func
    
    club_id = get_current_club_id()
    
    all_tickets = Ticket.query.order_by(Ticket.id).all()
    
    query = Meeting.query.filter(Meeting.status == 'finished', Meeting.Meeting_Number >= 951)
    if club_id:
        query = query.filter(Meeting.club_id == club_id)
    meetings = query.order_by(Meeting.Meeting_Number.asc()).all()
    meeting_numbers = [m.Meeting_Number for m in meetings]
    meeting_dates = [m.Meeting_Date.strftime('%Y-%m-%d') if m.Meeting_Date else '' for m in meetings]
    
    cancelled_ticket = Ticket.query.filter_by(name='Cancelled').first()
    cancelled_ticket_id = cancelled_ticket.id if cancelled_ticket else -1
    
    counts_query = db.session.query(
        Roster.meeting_number,
        Roster.ticket_id,
        func.count(Roster.id).label('count')
    ).filter(
        Roster.meeting_number.in_(meeting_numbers),
        Roster.ticket_id != cancelled_ticket_id
    ).group_by(
        Roster.meeting_number,
        Roster.ticket_id
    ).all()
    
    counts_by_meeting = {}
    for mtg_num, ticket_id, count in counts_query:
        if mtg_num not in counts_by_meeting:
            counts_by_meeting[mtg_num] = {}
        counts_by_meeting[mtg_num][ticket_id] = count
    
    datasets = []
    for ticket in all_tickets:
        if ticket.name == 'Cancelled':
            continue
        
        data = []
        for mtg_num in meeting_numbers:
            count = counts_by_meeting.get(mtg_num, {}).get(ticket.id, 0)
            data.append(count)
        
        if sum(data) > 0:
            datasets.append({
                'label': ticket.name,
                'data': data,
                'color': ticket.color or '#6c757d',
                'icon': ticket.icon or 'fa-ticket-alt'
            })
    
    return render_template('roster_participation_trend.html',
                           meeting_numbers=meeting_numbers,
                           meeting_dates=meeting_dates,
                           datasets=datasets)


@roster_bp.route('/api/entry', methods=['POST'])
@login_required
@authorized_club_required
def create_roster_entry():
    """Create a new roster entry"""
    data = request.get_json()

    required_fields = ['meeting_number', 'order_number', 'ticket']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    ticket_name = data['ticket']
    ticket_obj = Ticket.query.filter_by(name=ticket_name).first()
    if not ticket_obj:
         return jsonify({'error': f'Invalid ticket type: {ticket_name}'}), 400

    new_entry = Roster(
        meeting_number=data['meeting_number'],
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
        'ticket': entry.ticket.name if entry.ticket else None,
        'contact_id': entry.contact_id,
        'contact_name': contact_name,
        'contact_type': contact_type
    })


@roster_bp.route('/api/entry/<int:entry_id>', methods=['PUT'])
@login_required
@authorized_club_required
def update_roster_entry(entry_id):
    entry = db.session.get(Roster, entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404

    data = request.get_json()

    if 'order_number' in data:
        entry.order_number = data['order_number']
    if 'ticket' in data:
        ticket_name = data['ticket']
        ticket_obj = Ticket.query.filter_by(name=ticket_name).first()
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
    
    t_obj = Ticket.query.filter_by(name=ticket_name).first()
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
            cancelled_ticket = Ticket.query.filter_by(name='Cancelled').first()
            if cancelled_ticket:
                entry.ticket_id = cancelled_ticket.id
            message = 'Entry cancelled successfully'
            
        db.session.commit()
        return jsonify({'message': message}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

