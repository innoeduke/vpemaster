from flask import Blueprint, render_template, request, jsonify
from .auth.utils import login_required
from .models import Roster, Meeting, Contact
from . import db
from sqlalchemy import distinct

roster_bp = Blueprint('roster_bp', __name__)


@roster_bp.route('/', methods=['GET'])
@login_required
def roster():
    # Get current meeting logic, same as agenda page
    today = db.func.current_date()

    # Query future meetings
    future_meetings_q = Meeting.query.filter(
        Meeting.Meeting_Date >= today
    )

    # Query recent past meetings
    past_meetings_q = Meeting.query.filter(
        Meeting.Meeting_Date < today
    ).order_by(Meeting.Meeting_Date.desc()).limit(8)

    # Execute queries
    future_meetings = future_meetings_q.all()
    past_meetings = past_meetings_q.all()

    # Merge, sort and get meeting numbers
    all_meetings = sorted(
        future_meetings + past_meetings, key=lambda m: m.Meeting_Date, reverse=True)
    meeting_numbers = [m.Meeting_Number for m in all_meetings]

    selected_meeting_str = request.args.get('meeting_number')
    selected_meeting_num = None

    if selected_meeting_str:
        try:
            selected_meeting_num = int(selected_meeting_str)
        except ValueError:
            selected_meeting_num = None
    else:
        # Find the next upcoming meeting
        upcoming_meeting = Meeting.query\
            .filter(Meeting.Meeting_Date >= today)\
            .order_by(Meeting.Meeting_Date.asc(), Meeting.Meeting_Number.asc())\
            .first()

        if upcoming_meeting:
            selected_meeting_num = upcoming_meeting.Meeting_Number
        elif meeting_numbers:
            # Fallback to the most recent existing meeting
            selected_meeting_num = meeting_numbers[0]

    # Get the selected meeting
    selected_meeting = None
    roster_entries = []
    first_unallocated_entry = None
    next_unallocated_entry = None
    if selected_meeting_num:
        selected_meeting = Meeting.query.filter(
            Meeting.Meeting_Number == selected_meeting_num
        ).first()

        # Get roster entries for this meeting (including unallocated entries)
        roster_entries = Roster.query\
            .outerjoin(Contact, Roster.contact_id == Contact.id)\
            .filter(Roster.meeting_number == selected_meeting_num)\
            .order_by(Roster.order_number.asc())\
            .all()
                
        # Find next available order number (last order number + 1)
        next_unallocated_entry = None
        if roster_entries:
            valid_orders = [entry.order_number for entry in roster_entries if entry.order_number < 1000]
            max_order = max(valid_orders) if valid_orders else 0
            next_unallocated_entry = type('obj', (object,), {'order_number': max_order + 1})()
        else:
            next_unallocated_entry = type('obj', (object,), {'order_number': 1})()

        # Find the first unallocated entry (where contact is empty)
        for entry in roster_entries:
            if not entry.contact_id:
                first_unallocated_entry = entry
                break

    # Get all contacts for the dropdown menu
    contacts = Contact.query.order_by(Contact.Name).all()

    from .models import Pathway
    all_pathways = Pathway.query.filter_by(status='active').order_by(Pathway.name).all()
    pathways = {}
    for p in all_pathways:
        ptype = p.type or "Other"
        if ptype not in pathways:
            pathways[ptype] = []
        pathways[ptype].append(p.name)

    return render_template(
        'roster.html',
        all_meetings=all_meetings,
        selected_meeting=selected_meeting,
        selected_meeting_num=selected_meeting_num,
        roster_entries=roster_entries,
        contacts=contacts,
        meeting_numbers=meeting_numbers,
        next_unallocated_entry=next_unallocated_entry,
        pathways=pathways
    )


@roster_bp.route('/api/roster', methods=['POST'])
@login_required
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


@roster_bp.route('/api/roster/<int:entry_id>', methods=['GET'])
@login_required
def get_roster_entry(entry_id):
    entry = Roster.query.get(entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404
    
    contact_name = None
    contact_type = entry.contact_type

    if entry.contact:
        contact_name = entry.contact.Name
        if not contact_type:
            # Identify as Officer if linked user has an officer role
            if entry.contact.user and entry.contact.user.is_officer:
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


@roster_bp.route('/api/roster/<int:entry_id>', methods=['PUT'])
@login_required
def update_roster_entry(entry_id):
    entry = Roster.query.get(entry_id)
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


@roster_bp.route('/api/roster/<int:entry_id>', methods=['DELETE'])
@login_required
def cancel_roster_entry(entry_id):
    entry = Roster.query.get(entry_id)
    if not entry:
        return jsonify({'error': 'Entry not found'}), 404

    try:
        entry.ticket = 'Cancelled'
        db.session.commit()
        return jsonify({'message': 'Entry cancelled successfully'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
