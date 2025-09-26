# vpemaster/booking_routes.py
from flask import Blueprint, render_template, request, session, jsonify, redirect, url_for
from .main_routes import login_required
from .models import Meeting, SessionLog, SessionType, Contact, User
from vpemaster import db
from sqlalchemy import and_, or_
from datetime import date

booking_bp = Blueprint('booking_bp', __name__)

@booking_bp.route('/booking', methods=['GET'])
@booking_bp.route('/booking/<int:meeting_number>', methods=['GET'])
@login_required
def booking(meeting_number=None):
    user = User.query.get(session.get('user_id'))
    current_contact_id = user.Contact_ID if user else None
    user_role = session.get('user_role')

    today = date.today()
    upcoming_meetings_q = Meeting.query.filter(Meeting.Meeting_Date >= today).order_by(Meeting.Meeting_Date.asc()).all()
    upcoming_meetings = [{"number": m.Meeting_Number, "date": m.Meeting_Date.strftime('%Y-%m-%d')} for m in upcoming_meetings_q]

    selected_meeting = meeting_number
    if not selected_meeting and upcoming_meetings:
        selected_meeting = upcoming_meetings[0]['number']

    if not selected_meeting:
        return render_template('booking.html', roles=[], upcoming_meetings=upcoming_meetings, selected_meeting=None, contacts=[], user_role=user_role, current_contact_id=current_contact_id, user_bookings=[])

    all_roles_query = db.session.query(
        SessionType.Role,
        SessionLog.id.label("SessionLog_ID"),
        SessionLog.Owner_ID,
        Contact.Name.label("Owner"),
        SessionLog.Meeting_Seq
    ).join(SessionLog, SessionType.id == SessionLog.Type_ID) \
    .outerjoin(Contact, SessionLog.Owner_ID == Contact.id) \
    .filter(SessionLog.Meeting_Number == selected_meeting) \
    .filter(SessionType.Role != '') \
    .order_by(SessionLog.Meeting_Seq)

    roles_from_db = all_roles_query.all()

    # Logic to handle unique vs. repeatable roles
    deduplicated_roles = []
    seen_unique_roles = set()
    repeatable_keywords = ["Prepared Speaker", "Individual Evaluator"]

    for role in roles_from_db:
        is_repeatable = any(keyword in role.Role for keyword in repeatable_keywords)

        if is_repeatable:
            deduplicated_roles.append(role)
        else:
            if role.Role not in seen_unique_roles:
                deduplicated_roles.append(role)
                seen_unique_roles.add(role.Role)

    roles = deduplicated_roles

    if user_role not in ['Admin', 'VPE']:
        # Filter roles for members/officers
        roles = [
            role for role in roles
            if role.Owner_ID is None or role.Owner_ID == current_contact_id
        ]
        # Sort for members/officers
        def sort_key(role):
            if role.Owner_ID == current_contact_id:
                return 0  # My bookings
            if role.Owner_ID is None:
                return 1  # Available
            return 2
        roles.sort(key=sort_key)


    contacts = Contact.query.order_by(Contact.Name).all()

    user_bookings_q = db.session.query(
        SessionLog.Meeting_Number,
        Meeting.Meeting_Date,
        SessionType.Role
    ).join(Meeting, SessionLog.Meeting_Number == Meeting.Meeting_Number) \
    .join(SessionType, SessionLog.Type_ID == SessionType.id) \
    .filter(SessionLog.Owner_ID == current_contact_id) \
    .filter(Meeting.Meeting_Date >= today) \
    .order_by(Meeting.Meeting_Date.asc(), SessionLog.Meeting_Seq.asc()) \
    .distinct(SessionLog.Meeting_Number, SessionType.Role) \
    .all()

    role_icons = {
        "SAA": "fa-shield-alt", "President": "fa-crown", "TME": "fa-microphone-alt",
        "Ah-Counter": "fa-calculator", "Grammarian": "fa-book", "Timer": "fa-stopwatch",
        "Sharing Master": "fa-share-alt", "Topicmaster": "fa-comments",
        "Prepared Speaker": "fa-user-tie", "GE": "fa-search",
        "Individual Evaluator": "fa-pen-nib"
    }

    user_bookings = [{
        "Meeting_Number": b.Meeting_Number,
        "Meeting_Date": b.Meeting_Date,
        "Role": b.Role,
        "icon": role_icons.get(b.Role.split('(')[0].strip(), "fa-question-circle")
    } for b in user_bookings_q]

    roles_with_icons = [{
        "Role": r.Role,
        "SessionLog_ID": r.SessionLog_ID,
        "Owner_ID": r.Owner_ID,
        "Owner": r.Owner,
        "icon": role_icons.get(r.Role.split('(')[0].strip(), "fa-question-circle")
    } for r in roles]


    return render_template('booking.html', roles=roles_with_icons,
                           upcoming_meetings=upcoming_meetings,
                           selected_meeting=selected_meeting, contacts=contacts,
                           user_role=user_role, current_contact_id=current_contact_id,
                           user_bookings=user_bookings)


@booking_bp.route('/booking/update', methods=['POST'])
@login_required
def update_role():
    data = request.get_json()
    meeting_number = data.get('meeting_number')
    role_name = data.get('role')
    session_log_id = data.get('session_log_id')
    new_owner_id = data.get('new_owner_id')

    user = User.query.get(session.get('user_id'))
    current_contact_id = user.Contact_ID if user else None
    user_role = session.get('user_role')

    repeatable_keywords = ["Prepared Speaker", "Individual Evaluator"]
    is_repeatable = any(keyword in role_name for keyword in repeatable_keywords)

    if is_repeatable:
        # For repeatable roles, target the specific session log ID
        log_to_update = SessionLog.query.get(session_log_id)
        if not log_to_update:
            return jsonify(success=False, message="Session log not found.")
        logs_to_update = [log_to_update]
    else:
        # For unique roles, update all entries with that role name for the meeting
        logs_to_update = SessionLog.query.join(SessionType).filter(
            SessionLog.Meeting_Number == meeting_number,
            SessionType.Role == role_name
        ).all()

    if not logs_to_update:
        return jsonify(success=False, message="Role not found for this meeting.")

    for log in logs_to_update:
        if new_owner_id == 'cancel':
            if log.Owner_ID == current_contact_id or user_role in ['Admin', 'VPE']:
                log.Owner_ID = None
            else:
                return jsonify(success=False, message="You can only cancel your own bookings.")
        else:
            # Admins/VPEs can assign anyone, others can only book available roles
            if user_role in ['Admin', 'VPE']:
                log.Owner_ID = new_owner_id if new_owner_id else None
            elif log.Owner_ID is None:
                log.Owner_ID = new_owner_id
            else:
                return jsonify(success=False, message="This role is already booked.")

    db.session.commit()
    return jsonify(success=True)

