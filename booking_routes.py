# vpemaster/booking_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, current_app
from .main_routes import login_required
from .models import SessionLog, SessionType, Contact, Meeting, User
from vpemaster import db
from sqlalchemy import desc, case
from datetime import datetime, timedelta

booking_bp = Blueprint('booking_bp', __name__)

ROLE_ICONS = {
    "SAA": "fa-shield-alt",
    "President": "fa-crown",
    "TME": "fa-microphone",
    "Ah-Counter": "fa-calculator",
    "Grammarian": "fa-book",
    "Timer": "fa-stopwatch",
    "GE": "fa-search",
    "Topicmaster": "fa-comments",
    "Sharing Master": "fa-share-alt",
    "Prepared Speaker": "fa-user-tie",
    "Individual Evaluator": "fa-pen-square",
    "Keynote Speaker": "fa-star",
    "Default": "fa-question-circle"
}

def _get_roles_for_meeting(selected_meeting_number, user_role, current_user_contact_id):
    """Helper function to get and process roles for the booking page."""

    query = db.session.query(
        SessionLog.id.label('session_id'),
        SessionType.Role.label('role'),
        SessionLog.Session_Title,
        SessionLog.Owner_ID,
        Contact.Name.label('owner_name')
    ).join(SessionType, SessionLog.Type_ID == SessionType.id)\
     .outerjoin(Contact, SessionLog.Owner_ID == Contact.id)\
     .filter(SessionLog.Meeting_Number == selected_meeting_number)\
     .filter(SessionType.Role != '', SessionType.Role.isnot(None))

    session_logs = query.all()

    # Consolidate roles
    roles_dict = {}
    for log in session_logs:
        role_key = log.role

        # Roles that must always have unique entries (one row per session log):
        # Prepared Speaker and Individual Evaluator
        if role_key in ["Prepared Speaker", "Individual Evaluator"]:
            # --- Unique Slot Logic ---
            # 1. Determine Display Name
            # Check for specific "Evaluation for" title, gracefully handling Session_Title being None
            if role_key == "Individual Evaluator" and "Evaluation for" in (log.Session_Title or ''):
                speaker_name = log.Session_Title.replace("Evaluation for", "").strip()
                role_display = f"Individual Evaluator ({speaker_name})"
            else:
                role_display = role_key

            # 2. Use a unique key for each slot (session log ID)
            role_key_unique = f"{role_key}_{log.session_id}"

            # Create the entry - no consolidation needed for these roles
            roles_dict[role_key_unique] = {
                'role': role_display,
                'role_key': role_key,
                'owner_id': log.Owner_ID,
                'owner_name': log.owner_name,
                'session_ids': [log.session_id]
            }

        # Roles that are unique per meeting (SAA, TME, etc.) and should be consolidated
        else:
            role_display = role_key
            role_key_unique = role_key # The key is the role name

            if role_key_unique not in roles_dict:
                roles_dict[role_key_unique] = {
                    'role': role_display,
                    'role_key': role_key,
                    'owner_id': log.Owner_ID,
                    'owner_name': log.owner_name,
                    'session_ids': [log.session_id] # Store all associated session IDs
                }
            else:
                # Append session ID and update owner if a new one is found
                roles_dict[role_key_unique]['session_ids'].append(log.session_id)
                # If one of the sessions is assigned, the whole role is considered assigned
                if log.Owner_ID:
                    roles_dict[role_key_unique]['owner_id'] = log.Owner_ID
                    roles_dict[role_key_unique]['owner_name'] = log.owner_name

    # Convert dict to list and add icons
    roles_with_icons = []
    for key, role_data in roles_dict.items():
        role_data['icon'] = ROLE_ICONS.get(role_data['role_key'], ROLE_ICONS['Default'])
        # Use the first session_id for actions. The backend will handle finding all related ones.
        role_data['session_id'] = role_data['session_ids'][0]
        roles_with_icons.append(role_data)


    # Apply filtering and sorting
    if user_role not in ['Admin', 'VPE']:
        # Filter out roles booked by others
        roles_with_icons = [
            role for role in roles_with_icons
            if not role['owner_id'] or role['owner_id'] == current_user_contact_id
        ]

        # Recent speaker rule
        three_meetings_ago = selected_meeting_number - 2
        recent_speaker_log = db.session.query(SessionLog.id).join(SessionType)\
            .filter(SessionLog.Owner_ID == current_user_contact_id)\
            .filter(SessionType.Role == 'Prepared Speaker')\
            .filter(SessionLog.Meeting_Number >= three_meetings_ago)\
            .filter(SessionLog.Meeting_Number <= selected_meeting_number).first()

        if recent_speaker_log:
            # The rule should prevent booking a NEW speech, but not hide an existing one.
            # Keep roles that are NOT 'Prepared Speaker', OR keep the 'Prepared Speaker' role if it belongs to the current user.
            roles_with_icons = [
                role for role in roles_with_icons
                if role['role_key'] != 'Prepared Speaker' or (role['role_key'] == 'Prepared Speaker' and role['owner_id'] == current_user_contact_id)
            ]

        # Sort for members/officers: 1st your roles, 2nd available roles.
        roles_with_icons.sort(key=lambda x: (
            0 if x['owner_id'] == current_user_contact_id else 1 if not x['owner_id'] else 2,
            x['role']
        ))

        # Sort for members/officers
        roles_with_icons.sort(key=lambda x: (
            0 if x['owner_id'] == current_user_contact_id else 1 if not x['owner_id'] else 2,
            x['role']
        ))
    else:
        # Sort for VPE/Admin (by default meeting order)
         roles_with_icons.sort(key=lambda x: x['session_id'])

    return roles_with_icons


@booking_bp.route('/booking', defaults={'selected_meeting_number': None}, methods=['GET'])
@booking_bp.route('/booking/<int:selected_meeting_number>', methods=['GET'])
@login_required
def booking(selected_meeting_number):
    # Get user info
    user_role = session.get('user_role', 'Guest')
    user = User.query.get(session.get('user_id'))
    current_user_contact_id = user.Contact_ID if user else None

    # Get meeting info
    upcoming_meetings = db.session.query(Meeting.Meeting_Number, Meeting.Meeting_Date)\
        .filter(Meeting.Meeting_Date >= datetime.today().date())\
        .order_by(Meeting.Meeting_Number.asc()).all()

    if not selected_meeting_number and upcoming_meetings:
        selected_meeting_number = upcoming_meetings[0][0]

    if not selected_meeting_number:
        return render_template('booking.html', roles=[], upcoming_meetings=[], selected_meeting_number=None, user_bookings_by_date=[], contacts=[])

    # Get roles for the selected meeting
    roles_with_icons = _get_roles_for_meeting(selected_meeting_number, user_role, current_user_contact_id)

    # Get user's upcoming roles for the timeline
    user_bookings_query = db.session.query(
        SessionLog.id,
        SessionType.Role,
        Meeting.Meeting_Number,
        Meeting.Meeting_Date
    ).join(SessionType, SessionLog.Type_ID == SessionType.id)\
     .join(Meeting, SessionLog.Meeting_Number == Meeting.Meeting_Number)\
     .filter(SessionLog.Owner_ID == current_user_contact_id)\
     .filter(Meeting.Meeting_Date >= datetime.today().date())\
     .filter(SessionType.Role != '', SessionType.Role.isnot(None))\
     .order_by(Meeting.Meeting_Date, SessionType.Role).distinct()

    user_bookings = user_bookings_query.all()

    # Process for timeline display
    user_bookings_by_date = {}
    processed_roles = set()

    for log in user_bookings:
        # This check prevents double counting
        role_meeting_key = (log.Meeting_Number, log.Role)
        if role_meeting_key in processed_roles:
            continue
        processed_roles.add(role_meeting_key)

        date_str = log.Meeting_Date.strftime('%Y-%m-%d')
        if date_str not in user_bookings_by_date:
            user_bookings_by_date[date_str] = {
                'date_info': {
                    'meeting_number': log.Meeting_Number,
                    'short_date': log.Meeting_Date.strftime('%m-%d')
                },
                'bookings': []
            }

        user_bookings_by_date[date_str]['bookings'].append({
            'role': log.Role, # Use the logical Role
            'role_key': log.Role, # Pass the logical Role as the key
            'icon': ROLE_ICONS.get(log.Role, ROLE_ICONS['Default']),
            'session_id': log.id
        })

    user_bookings_timeline = sorted(user_bookings_by_date.values(), key=lambda x: x['date_info']['meeting_number'])

    # Get contacts for admin dropdown
    contacts = Contact.query.order_by(Contact.Name).all()

    return render_template('booking.html',
                           roles=roles_with_icons,
                           upcoming_meetings=upcoming_meetings,
                           selected_meeting_number=selected_meeting_number,
                           is_vpe_or_admin=(user_role in ['Admin', 'VPE']),
                           current_user_contact_id=current_user_contact_id,
                           user_bookings_by_date=user_bookings_timeline,
                           contacts=contacts)


@booking_bp.route('/booking/book', methods=['POST'])
@login_required
def book_or_assign_role():
    data = request.get_json()
    session_id = data.get('session_id')
    action = data.get('action')
    role_key = data.get('role_key')

    user = User.query.get(session.get('user_id'))
    current_user_contact_id = user.Contact_ID if user else None
    user_role = session.get('user_role')

    log = SessionLog.query.get(session_id)
    if not log:
        return jsonify(success=False, message="Session not found.")

    # Find all session logs for this role in this meeting
    sessions_to_update = SessionLog.query.join(SessionType)\
        .filter(SessionLog.Meeting_Number == log.Meeting_Number)\
        .filter(SessionType.Role == role_key).all()

    if not sessions_to_update:
        return jsonify(success=False, message="No matching roles found to update.")

    owner_id_to_set = None
    if action == 'book':
        owner_id_to_set = current_user_contact_id
    elif action == 'cancel':
        owner_id_to_set = None
    elif action == 'assign' and user_role in ['Admin', 'VPE']:
        contact_id = data.get('contact_id', '0')
        owner_id_to_set = int(contact_id) if contact_id != '0' else None

    # For repeatable roles, only update the specific session
    if role_key in ["Prepared Speaker", "Individual Evaluator"]:
        log_to_update = SessionLog.query.get(session_id)
        if log_to_update:
            log_to_update.Owner_ID = owner_id_to_set
    else: # For unique roles, update all associated sessions
        for session_log in sessions_to_update:
            session_log.Owner_ID = owner_id_to_set

    try:
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e))