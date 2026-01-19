from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
from .models import Roster, Meeting, Contact, ContactClub, Pathway
from .club_context import get_current_club_id, authorized_club_required
from . import db
from sqlalchemy import distinct
from .utils import get_meetings_by_status
from .constants import RoleID

tools_bp = Blueprint('tools_bp', __name__)

@tools_bp.route('/', methods=['GET'])
@login_required
@authorized_club_required
def tools():
    # Check if user has permission to view EITHER Roster or Lucky Draw
    has_roster_access = is_authorized(Permissions.ROSTER_VIEW)
    has_lucky_draw_access = is_authorized(Permissions.LUCKY_DRAW_VIEW)

    if not (has_roster_access or has_lucky_draw_access):
         return redirect(url_for('agenda_bp.agenda'))

    # Determine Active Tab
    active_tab = request.args.get('tab')
    
    # Heuristics for default tab if not specified
    if not active_tab:
        if request.args.get('meeting_number') and has_roster_access:
            active_tab = 'roster'
        elif has_lucky_draw_access:
            active_tab = 'luckydraw'
        elif has_roster_access:
            active_tab = 'roster'
            
    # Validate access to requested tab
    if active_tab == 'luckydraw' and not has_lucky_draw_access:
        active_tab = 'roster' if has_roster_access else None
    elif active_tab == 'roster' and not has_roster_access:
        active_tab = 'luckydraw' if has_lucky_draw_access else None
        
    if not active_tab:
         return redirect(url_for('agenda_bp.agenda'))

    # Init Context Variables
    ld_current_meeting = None
    ld_entries = []
    
    all_meetings = []
    selected_meeting = None
    selected_meeting_num = None
    roster_entries = []
    contacts = []
    next_unallocated_entry = None
    pathways = {}
    meeting_numbers = []

    # Load Data for Active Tab Only
    club_id = get_current_club_id()
    today = db.func.current_date()

    if active_tab == 'luckydraw':
        # Find the next upcoming meeting
        ld_query = Meeting.query.filter(Meeting.Meeting_Date >= today)
        if club_id:
            ld_query = ld_query.filter(Meeting.club_id == club_id)
            
        ld_current_meeting = ld_query.order_by(Meeting.Meeting_Date.asc(), Meeting.Meeting_Number.asc()).first()

        # If no upcoming meeting, get the most recent past meeting
        if not ld_current_meeting:
            ld_past_query = Meeting.query.filter(Meeting.Meeting_Date < today)
            if club_id:
                ld_past_query = ld_past_query.filter(Meeting.club_id == club_id)
            ld_current_meeting = ld_past_query.order_by(Meeting.Meeting_Date.desc()).first()

        # Get roster entries for this meeting (excluding cancelled entries)
        if ld_current_meeting:
            ld_entries = Roster.query\
                .options(db.joinedload(Roster.roles))\
                .outerjoin(Contact, Roster.contact_id == Contact.id)\
                .filter(Roster.meeting_number == ld_current_meeting.Meeting_Number)\
                .filter(Roster.ticket != 'Cancelled')\
                .order_by(Roster.order_number.asc())\
                .all()

    elif active_tab == 'roster':
        all_meetings, default_meeting_num = get_meetings_by_status(limit_past=8)
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

        if selected_meeting_num:
            query = Meeting.query.filter(Meeting.Meeting_Number == selected_meeting_num)
            if club_id:
                query = query.filter(Meeting.club_id == club_id)
            selected_meeting = query.first()

            # Get roster entries for this meeting (including unallocated entries)
            roster_entries = Roster.query\
                .options(db.joinedload(Roster.roles))\
                .outerjoin(Contact, Roster.contact_id == Contact.id)\
                .filter(Roster.meeting_number == selected_meeting_num)\
                .order_by(Roster.order_number.asc())\
                .all()
                    
            # Find next available order number (last order number + 1)
            if roster_entries:
                valid_orders = [entry.order_number for entry in roster_entries if entry.order_number is not None and entry.order_number < 1000]
                max_order = max(valid_orders) if valid_orders else 0
                next_unallocated_entry = type('obj', (object,), {'order_number': max_order + 1})()
            else:
                next_unallocated_entry = type('obj', (object,), {'order_number': 1})()

        # Get all contacts for the dropdown menu, filtered by club
        contacts = Contact.query.join(ContactClub).filter(ContactClub.club_id == club_id)\
            .order_by(Contact.Name).all()

        all_pathways = Pathway.query.filter_by(status='active').order_by(Pathway.name).all()
        for p in all_pathways:
            ptype = p.type or "Other"
            if ptype not in pathways:
                pathways[ptype] = []
            pathways[ptype].append(p.name)

    return render_template(
        'tools.html',
        active_tab=active_tab,
        has_lucky_draw_access=has_lucky_draw_access,
        has_roster_access=has_roster_access,
        # Lucky Draw Context
        ld_current_meeting=ld_current_meeting,
        ld_entries=ld_entries,
        RoleID=RoleID,
        # Roster Context
        all_meetings=all_meetings,
        selected_meeting=selected_meeting,
        selected_meeting_num=selected_meeting_num,
        roster_entries=roster_entries,
        contacts=contacts,
        meeting_numbers=meeting_numbers,
        next_unallocated_entry=next_unallocated_entry,
        pathways=pathways
    )

# --- API Endpoints (Moved from roster_routes.py) ---

@tools_bp.route('/api/roster', methods=['POST'])
@login_required
@authorized_club_required
def create_roster_entry():
    """Create a new roster entry"""
    data = request.get_json()

    required_fields = ['meeting_number', 'order_number', 'ticket']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'error': f'Missing required field: {field}'}), 400

    new_entry = Roster(
        meeting_number=data['meeting_number'],
        order_number=data['order_number'],
        ticket=data['ticket']
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


@tools_bp.route('/api/roster/<int:entry_id>', methods=['GET'])
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
        if not contact_type:
            # Identify as Officer if linked user has an officer role
            if entry.contact.user and entry.contact.user.has_role(Permissions.STAFF):
                contact_type = 'Officer'
            else:
                contact_type = entry.contact.Type

    return jsonify({
        'id': entry.id,
        'meeting_number': entry.meeting_number,
        'order_number': entry.order_number,
        'ticket': entry.ticket,
        'contact_id': entry.contact_id,
        'contact_name': contact_name,
        'contact_type': contact_type
    })


@tools_bp.route('/api/roster/<int:entry_id>', methods=['PUT'])
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
        entry.ticket = data['ticket']

    if 'contact_id' in data:
        if data['contact_id']:  # If contact_id is not empty
            entry.contact_id = data['contact_id']
        else:  # If contact_id is empty, set to None
            entry.contact_id = None
            
    if 'contact_type' in data:
        entry.contact_type = data['contact_type']

    try:
        db.session.commit()
        return jsonify({'message': 'Entry updated successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@tools_bp.route('/api/roster/<int:entry_id>', methods=['DELETE'])
@login_required
@authorized_club_required
def delete_roster_entry(entry_id):
    entry = db.session.get(Roster, entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404

    hard_delete = request.args.get('hard_delete') == 'true'

    try:
        if hard_delete:
            # Delete associated roles first
            from .models.roster import RosterRole
            RosterRole.query.filter_by(roster_id=entry_id).delete()
            db.session.delete(entry)
            message = 'Entry deleted successfully'
        else:
            entry.ticket = 'Cancelled'
            message = 'Entry cancelled successfully'
            
        db.session.commit()
        return jsonify({'message': message}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
