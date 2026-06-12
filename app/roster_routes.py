from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from datetime import datetime
from flask_login import current_user
from .translations.translations import translate as _
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


@roster_bp.before_request
def check_roster_enabled():
    from app.club_context import is_module_enabled
    from flask import abort
    if not is_module_enabled('Roster'):
        abort(404)


@roster_bp.route('/', methods=['GET'])
@login_required
@authorized_club_required
def roster():
    """Independent roster page"""
    # Get meeting first to allow context-aware authorization
    club_id = get_current_club_id()
    selected_meeting_id_str = request.args.get('meeting_id')
    selected_meeting = None
    
    if selected_meeting_id_str:
        try:
            selected_meeting_id = int(selected_meeting_id_str)
            selected_meeting = db.session.get(Meeting, selected_meeting_id)
        except (ValueError, TypeError):
            selected_meeting_id = None
    else:
        from .utils import get_default_meeting_id
        selected_meeting_id = get_default_meeting_id()
        if selected_meeting_id:
            selected_meeting = db.session.get(Meeting, selected_meeting_id)

    if not is_authorized(Permissions.ROSTER_VIEW, meeting=selected_meeting):
        return redirect(url_for('agenda_bp.agenda'))

    club_id = get_current_club_id()
    
    is_guest = current_user.is_guest_of_club(club_id)
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

    # Build set of officer contact IDs from ContactClub.is_officer
    officer_contact_ids = set(
        cc.contact_id for cc in ContactClub.query.filter_by(club_id=club_id, is_officer=True).all()
    )

    selected_meeting = None
    roster_entries = []
    roles_map = {}
    next_unallocated_entry = None
    
    if selected_meeting_id:
        selected_meeting = Meeting.query.get(selected_meeting_id)
        if selected_meeting and (club_id and selected_meeting.club_id != club_id):
             selected_meeting = None
 
        if selected_meeting:
            Roster.convert_expired_early_birds(selected_meeting_id)

            # Get roster entries for this meeting (including unallocated entries)
            roster_entries = Roster.query\
                .options(db.joinedload(Roster.roles), db.joinedload(Roster.ticket))\
                .outerjoin(Contact, Roster.contact_id == Contact.id)\
                .filter(Roster.meeting_id == selected_meeting_id)\
                .all()
                
            def get_sort_key(entry):
                name = entry.contact.Name if entry.contact else ""
                return (entry.order_number is None, entry.order_number or 0, name.lower())
                
            roster_entries.sort(key=get_sort_key)
        
        # Roles map
        roles_map = RoleService.get_role_takers(selected_meeting_id, club_id)
                
        
        # Calculate total amount and attendees
        total_amount = sum(entry.amount for entry in roster_entries if entry.amount)
        total_attendees = sum(1 for entry in roster_entries if entry.ticket and entry.ticket.name != 'Cancelled')

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
        officer_contact_ids=officer_contact_ids,
        next_unallocated_entry=next_unallocated_entry,
        pathways=pathways,
        tickets=tickets,
        tickets_map=tickets_map,
        RoleID=RoleID,
        total_amount=total_amount if 'total_amount' in locals() else 0,
        total_attendees=total_attendees if 'total_attendees' in locals() else 0,
        now=datetime.now(),
        datetime=datetime
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
                'label': _(name),
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
def create_roster_entry():
    """Create a new roster entry"""
    data = request.get_json()

    required_fields = ['meeting_id', 'ticket_id']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    # Authorization Check (including Meeting Manager override)
    selected_meeting = db.session.get(Meeting, data['meeting_id'])
    if not is_authorized(Permissions.ROSTER_EDIT, meeting=selected_meeting):
        return jsonify({'error': 'Unauthorized'}), 403

    ticket_id = data['ticket_id']
    ticket_obj = db.session.get(Ticket, ticket_id)
    if not ticket_obj:
         return jsonify({'error': f'Invalid ticket id: {ticket_id}'}), 400

    order_number = data.get('order_number') if data.get('order_number') not in [None, '', 'null'] else None

    existing_entry = None
    if 'contact_id' in data and data['contact_id']:
        existing_entry = Roster.query.filter_by(
            meeting_id=data['meeting_id'],
            contact_id=data['contact_id']
        ).filter(Roster.order_number.is_(None)).first()

    if existing_entry:
        existing_entry.order_number = order_number
        existing_entry.ticket_id = ticket_obj.id
        existing_entry.quantity = int(data.get('quantity', 1))
        if 'contact_type' in data:
            existing_entry.contact_type = data['contact_type']
        
        try:
            db.session.commit()
            return jsonify({'message': 'Entry created successfully', 'id': existing_entry.id}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500

    new_entry = Roster(
        meeting_id=data['meeting_id'],
        order_number=order_number,
        ticket_id=ticket_obj.id,
        quantity=int(data.get('quantity', 1))
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
    club_id = get_current_club_id()

    if entry.contact:
        contact_name = entry.contact.Name
        cc = ContactClub.query.filter_by(contact_id=entry.contact_id, club_id=club_id).first()
        if cc and cc.is_officer:
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
        'contact_type': contact_type,
        'quantity': entry.quantity,
        'checked_in_at': entry.checked_in_at.isoformat() if entry.checked_in_at else None,
        'checked_in_via': entry.checked_in_via,
        'checked_in_by': entry.checked_in_by.display_name if entry.checked_in_by else None,
    })


@roster_bp.route('/api/entry/<int:entry_id>', methods=['PUT'])
@login_required
@authorized_club_required
def update_roster_entry(entry_id):
    entry = db.session.get(Roster, entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404

    # Authorization Check (including Meeting Manager override)
    if not is_authorized(Permissions.ROSTER_EDIT, meeting=entry.meeting):
        return jsonify({'error': 'Unauthorized'}), 403

    data = request.get_json()

    if 'order_number' in data:
        val = data['order_number']
        entry.order_number = val if val not in [None, '', 'null'] else None
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
    if 'quantity' in data:
        entry.quantity = int(data['quantity'])

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

    # Authorization Check (including Meeting Manager override)
    if not is_authorized(Permissions.ROSTER_EDIT, meeting=entry.meeting):
        return jsonify({'error': 'Unauthorized'}), 403

    if entry.contact_type == 'Officer':
        t_obj = Ticket.get_by_name('Officer', type='Officer', club_id=entry.meeting.club_id if entry.meeting else None)
    elif entry.contact and entry.contact.Type == 'Member':
        t_obj = Ticket.get_by_name('Early-bird', type='Member', club_id=entry.meeting.club_id if entry.meeting else None)
    elif entry.contact and entry.contact.Type == 'Guest':
        t_obj = Ticket.get_by_name('Role-taker', type='Guest', club_id=entry.meeting.club_id if entry.meeting else None)
    else:
        t_obj = Ticket.get_by_name('Walk-in', type='Guest', club_id=entry.meeting.club_id if entry.meeting else None)
    
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

    # Authorization Check (including Meeting Manager override)
    if not is_authorized(Permissions.ROSTER_EDIT, meeting=entry.meeting):
        return jsonify({'error': 'Unauthorized'}), 403

    hard_delete = request.args.get('hard_delete') == 'true'

    try:
        if hard_delete:
            from .models.roster import RosterRole
            from .models.session import OwnerMeetingRoles
            
            # Release any booked roles in the agenda for this meeting
            OwnerMeetingRoles.query.filter_by(
                meeting_id=entry.meeting_id,
                contact_id=entry.contact_id
            ).delete(synchronize_session=False)

            # Remove associated roster roles and the entry itself
            RosterRole.query.filter_by(roster_id=entry_id).delete()
            db.session.delete(entry)
            message = 'Entry deleted successfully'
        else:
            cancelled_ticket = Ticket.get_by_name('Cancelled', club_id=entry.meeting.club_id if entry.meeting else None)
            if cancelled_ticket:
                entry.ticket_id = cancelled_ticket.id
            message = 'Entry cancelled successfully'
            
        db.session.commit()
        return jsonify({'message': message}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ---------------------------------------------------------------------------
# Self Check-In: officer-side endpoints (QR generation + manual toggle).
# The public check-in surface lives in app/checkin_routes.py.
# ---------------------------------------------------------------------------

def _checkin_meeting_in_club(meeting_id):
    """Helper: load the meeting only if it belongs to the current club."""
    meeting = db.session.get(Meeting, meeting_id)
    club_id = get_current_club_id()
    if not meeting or (club_id and meeting.club_id != club_id):
        return None
    return meeting


@roster_bp.route('/api/checkin/url/<int:meeting_id>', methods=['GET'])
@login_required
@authorized_club_required
def get_checkin_url(meeting_id):
    """Returns a freshly-signed check-in URL + token for officers to embed in
    the QR modal (so the modal can show both the QR and a copy-paste link)."""
    from app.club_context import is_module_enabled
    from .services.checkin_service import generate_checkin_token

    meeting = _checkin_meeting_in_club(meeting_id)
    if not meeting:
        return jsonify({'error': 'Meeting not found'}), 404
    if not is_authorized(Permissions.ROSTER_EDIT, meeting=meeting):
        return jsonify({'error': 'Unauthorized'}), 403
    if not is_module_enabled('Self Check-In', meeting.club_id):
        return jsonify({'error': 'Self Check-In module is disabled'}), 404
    if meeting.status not in ('not started', 'running'):
        return jsonify({'error': 'Meeting is not active'}), 400

    token = generate_checkin_token(meeting.id)
    url = url_for('checkin_bp.checkin_page', token=token, _external=True)
    
    # Generate Base64 QR code to avoid mobile WeChat re-fetch auth issues
    import qrcode
    from io import BytesIO
    import base64
    
    img = qrcode.make(url, box_size=10, border=4)
    buf = BytesIO()
    img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    qr_data_uri = f"data:image/png;base64,{qr_b64}"

    return jsonify({
        'url': url, 
        'token': token, 
        'expires_in': 24 * 60 * 60,
        'qr_data_uri': qr_data_uri
    })


@roster_bp.route('/api/checkin/qr/<int:meeting_id>', methods=['GET'])
@login_required
@authorized_club_required
def get_checkin_qr(meeting_id):
    """Returns a PNG QR code that encodes the check-in URL for this meeting."""
    from io import BytesIO

    import qrcode
    from flask import send_file

    from app.club_context import is_module_enabled
    from .services.checkin_service import generate_checkin_token

    meeting = _checkin_meeting_in_club(meeting_id)
    if not meeting:
        return jsonify({'error': 'Meeting not found'}), 404
    if not is_authorized(Permissions.ROSTER_EDIT, meeting=meeting):
        return jsonify({'error': 'Unauthorized'}), 403
    if not is_module_enabled('Self Check-In', meeting.club_id):
        return jsonify({'error': 'Self Check-In module is disabled'}), 404
    if meeting.status not in ('not started', 'running'):
        return jsonify({'error': 'Meeting is not active'}), 400

    token = generate_checkin_token(meeting.id)
    url = url_for('checkin_bp.checkin_page', token=token, _external=True)

    img = qrcode.make(url)
    buf = BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    response = send_file(buf, mimetype='image/png')
    response.headers['Cache-Control'] = 'private, max-age=60'
    return response


@roster_bp.route('/api/entry/<int:entry_id>/checkin', methods=['POST'])
@login_required
@authorized_club_required
def toggle_roster_checkin(entry_id):
    """Officer-side check-in toggle. Flips checked_in_at between now and None;
    records the officer who did it so the badge tooltip can show attribution."""
    entry = db.session.get(Roster, entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404

    if not is_authorized(Permissions.ROSTER_EDIT, meeting=entry.meeting):
        return jsonify({'error': 'Unauthorized'}), 403

    if entry.checked_in_at:
        entry.checked_in_at = None
        entry.checked_in_via = None
        entry.checked_in_by_user_id = None
    else:
        entry.checked_in_at = datetime.utcnow()
        entry.checked_in_via = 'officer'
        entry.checked_in_by_user_id = current_user.id

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

    return jsonify({
        'checked_in_at': entry.checked_in_at.isoformat() if entry.checked_in_at else None,
        'checked_in_via': entry.checked_in_via,
        'checked_in_by': entry.checked_in_by.display_name if entry.checked_in_by else None,
    })
