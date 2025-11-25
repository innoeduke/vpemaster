# vpemaster/booking_routes.py

from .auth.utils import login_required, is_authorized
from flask import Blueprint, render_template, request, session, jsonify, current_app
from .models import SessionLog, SessionType, Contact, Meeting, User, LevelRole, Waitlist, Role
from . import db
from datetime import datetime
import re
from sqlalchemy import or_
from .utils import derive_current_path_level, derive_designation


booking_bp = Blueprint('booking_bp', __name__)


def _fetch_session_logs(selected_meeting_number, user_role):
    """Fetches session logs for a given meeting, filtering by user role."""
    query = db.session.query(
        SessionLog.id.label('session_id'),
        Role.name.label('role'),
        Role.icon.label('icon'),
        SessionLog.Session_Title,
        SessionLog.Type_ID.label('type_id'),
        SessionLog.Owner_ID,
        Contact.Name.label('owner_name')
    ).join(SessionType, SessionLog.Type_ID == SessionType.id)\
     .join(Role, SessionType.role_id == Role.id)\
     .outerjoin(Contact, SessionLog.Owner_ID == Contact.id)\
     .filter(SessionLog.Meeting_Number == selected_meeting_number)\
     .filter(Role.name != '', Role.name.isnot(None))

    if not is_authorized(user_role, 'BOOKING_ASSIGN_ALL'):
        query = query.filter(Role.type != 'officer')

    return query.all()


def _consolidate_roles(session_logs, is_admin_booker):
    """Consolidates session logs into a dictionary of roles."""
    roles_dict = {}
    # unique role means only one person can take this role of a specific meeting
    non_distinct_role_records = Role.query.filter_by(is_distinct=False).all()
    non_distinct_roles = [role.name for role in non_distinct_role_records]
    non_distinct_roles = list(set(non_distinct_roles))

    for log in session_logs:
        role_key = log.role.strip() if log.role else ""
        if not role_key:
            continue

        waitlisted_users = db.session.query(Contact.Name, Contact.id).join(Waitlist).filter(
            Waitlist.session_log_id == log.session_id).order_by(Waitlist.timestamp).all()
        waitlisted_info = [{'name': user[0], 'id': user[1]}
                           for user in waitlisted_users]

        if role_key in non_distinct_roles:
            role_key_distinct = f"{role_key}_{log.session_id}"
            speaker_name = log.Session_Title.strip(
            ) if role_key == "Individual Evaluator" and log.Session_Title else None
            roles_dict[role_key_distinct] = {
                'role': role_key,
                'role_key': role_key,
                'owner_id': log.Owner_ID,
                'owner_name': log.owner_name,
                'session_ids': [log.session_id],
                'type_id': log.type_id,
                'speaker_name': speaker_name,
                'waitlist': waitlisted_info,
            }
        else:
            if role_key not in roles_dict:
                roles_dict[role_key] = {
                    'role': role_key,
                    'role_key': role_key,
                    'owner_id': log.Owner_ID,
                    'owner_name': log.owner_name,
                    'session_ids': [log.session_id],
                    'type_id': log.type_id,
                    'speaker_name': None,
                    'waitlist': waitlisted_info,
                }
            else:
                roles_dict[role_key]['session_ids'].append(log.session_id)
                if log.Owner_ID:
                    roles_dict[role_key]['owner_id'] = log.Owner_ID
                    roles_dict[role_key]['owner_name'] = log.owner_name
                # Append waitlisted users, avoiding duplicates
                existing_ids = {user['id']
                                for user in roles_dict[role_key]['waitlist']}
                for user_info in waitlisted_info:
                    if user_info['id'] not in existing_ids:
                        roles_dict[role_key]['waitlist'].append(user_info)
    return roles_dict


def _enrich_role_data(roles_dict, selected_meeting):
    """Enriches role data with icons and award information."""
    if not selected_meeting:
        return []

    award_ids = {
        'speaker': selected_meeting.best_speaker_id,
        'evaluator': selected_meeting.best_evaluator_id,
        'table-topic': selected_meeting.best_table_topic_id,
        'role-taker': selected_meeting.best_role_taker_id,
    }

    enriched_roles = []
    for _, role_data in roles_dict.items():
        role_obj = Role.query.filter_by(name=role_data['role_key']).first()

        role_data['icon'] = role_obj.icon if role_obj and role_obj.icon else "fa-question-circle"
        role_data['session_id'] = role_data['session_ids'][0]

        owner_id = role_data['owner_id']
        award_category = role_obj.award_category if role_obj else None

        role_data['award_category'] = award_category
        role_data['award_type'] = award_category if owner_id and award_category and owner_id == award_ids.get(
            award_category) else None
        role_data['award_category_open'] = bool(
            award_category and not award_ids.get(award_category))

        enriched_roles.append(role_data)
    return enriched_roles


def _apply_user_filters_and_rules(roles, user_role, current_user_contact_id, selected_meeting_number):
    """Applies filtering and business rules based on user permissions."""
    if is_authorized(user_role, 'BOOKING_ASSIGN_ALL'):
        return roles

    # Backup Speaker Rule
    if current_user_contact_id:
        has_upcoming_backup_speaker = db.session.query(SessionLog.id)\
            .join(Meeting, SessionLog.Meeting_Number == Meeting.Meeting_Number)\
            .join(SessionType, SessionLog.Type_ID == SessionType.id)\
            .join(Role, SessionType.role_id == Role.id)\
            .filter(SessionLog.Owner_ID == current_user_contact_id)\
            .filter(Role.name == current_app.config['ROLES']['BACKUP_SPEAKER']['name'])\
            .filter(Meeting.Meeting_Date >= datetime.today().date())\
            .first()
        if has_upcoming_backup_speaker:
            roles = [
                r for r in roles
                if r['role_key'] != current_app.config['ROLES']['BACKUP_SPEAKER']['name'] or (r['role_key'] == current_app.config['ROLES']['BACKUP_SPEAKER']['name'] and r['owner_id'] == current_user_contact_id)
            ]

    # 3-Week Policy speaker rule
    user = User.query.filter_by(Contact_ID=current_user_contact_id).first()
    if user and user.Current_Path:
        three_meetings_ago = selected_meeting_number - 2
        recent_speaker_log = db.session.query(SessionLog.id).join(SessionType).join(Role, SessionType.role_id == Role.id)\
            .filter(SessionLog.Owner_ID == current_user_contact_id)\
            .filter(Role.name == current_app.config['ROLES']['PREPARED_SPEAKER']['name'])\
            .filter(SessionLog.Meeting_Number.between(three_meetings_ago, selected_meeting_number)).first()

        if recent_speaker_log:
            roles = [
                r for r in roles
                if r['role_key'] != current_app.config['ROLES']['PREPARED_SPEAKER']['name'] or (r['role_key'] == current_app.config['ROLES']['PREPARED_SPEAKER']['name'] and r['owner_id'] == current_user_contact_id)
            ]

    return roles


def _sort_roles(roles, user_role, current_user_contact_id, is_past_meeting):
    """Sorts roles based on user type."""
    if is_past_meeting:
        # For past meetings, sort by award category first, then role name
        roles.sort(key=lambda x: (
            x.get('award_category', '') or '', x['role']))
    elif is_authorized(user_role, 'BOOKING_ASSIGN_ALL'):
        # For admin view of current/future meetings, sort by award category first, then role name
        roles.sort(key=lambda x: (
            x.get('award_category', '') or '', x['role']))
    else:  # For current/future meetings for non-admins
        roles.sort(key=lambda x: (
            0 if x['owner_id'] == current_user_contact_id else 1 if not x['owner_id'] else 2,
            x['role']
        ))
    return roles


def _get_roles_for_meeting(selected_meeting_number, user_role, current_user_contact_id, selected_meeting, is_past_meeting):
    """Helper function to get and process roles for the booking page."""
    is_admin_booker = is_authorized(user_role, 'BOOKING_ASSIGN_ALL')

    session_logs = _fetch_session_logs(selected_meeting_number, user_role)
    roles_dict = _consolidate_roles(session_logs, is_admin_booker)
    enriched_roles = _enrich_role_data(roles_dict, selected_meeting)
    filtered_roles = _apply_user_filters_and_rules(
        enriched_roles, user_role, current_user_contact_id, selected_meeting_number)

    sorted_roles = _sort_roles(
        filtered_roles, user_role, current_user_contact_id, is_past_meeting)

    if selected_meeting.status in ['running', 'finished']:
        sorted_roles = [role for role in sorted_roles if role.get(
            'award_category') and role.get('award_category') != 'none']

    return sorted_roles


def _get_user_info():
    """Gets user information from the session."""
    user_id = session.get('user_id')
    user = User.query.get(user_id) if user_id else None
    user_role = session.get('user_role', 'Guest')
    current_user_contact_id = user.Contact_ID if user else None
    return user, user_role, current_user_contact_id


def _get_default_level(user):
    """Determines the default project level for a user."""
    if user and user.Next_Project:
        match = re.match(r"([A-Z]+)(\d+)\.?(\d*)", user.Next_Project)
        if match:
            try:
                return int(match.group(2))
            except (ValueError, IndexError):
                pass
    return 1


def _get_meetings(user_role):
    """Fetches meetings based on user role."""
    today = datetime.today().date()

    soonest_upcoming_meeting = db.session.query(Meeting.Meeting_Number)\
        .filter(Meeting.Meeting_Date >= today)\
        .order_by(Meeting.Meeting_Number.asc())\
        .first()

    default_meeting_num = soonest_upcoming_meeting[0] if soonest_upcoming_meeting else None

    # Fetch all upcoming meetings, ordered with the soonest first.
    future_meetings = db.session.query(Meeting.Meeting_Number, Meeting.Meeting_Date)\
        .filter(Meeting.Meeting_Date >= today)\
        .order_by(Meeting.Meeting_Number.desc()).all()
    # Fetch the 5 most recent past meetings.
    past_meetings = db.session.query(Meeting.Meeting_Number, Meeting.Meeting_Date)\
        .filter(Meeting.Meeting_Date < today)\
        .order_by(Meeting.Meeting_Number.desc())\
        .limit(5).all()
    meetings = sorted(future_meetings + past_meetings,
                      key=lambda m: m[0], reverse=True)
    return meetings, default_meeting_num


def _get_user_bookings(current_user_contact_id):
    """Fetches and processes a user's upcoming bookings."""
    if not current_user_contact_id:
        return []

    today = datetime.today().date()
    user_bookings_query = db.session.query(
        db.func.min(SessionLog.id).label('id'),
        Role.name,
        Meeting.Meeting_Number,
        Meeting.Meeting_Date
    ).join(SessionType, SessionLog.Type_ID == SessionType.id)\
     .join(Role, SessionType.role_id == Role.id)\
     .join(Meeting, SessionLog.Meeting_Number == Meeting.Meeting_Number)\
     .filter(SessionLog.Owner_ID == current_user_contact_id)\
     .filter(Meeting.Meeting_Date >= today)\
     .filter(Role.name != '', Role.name.isnot(None))\
     .group_by(Meeting.Meeting_Number, Role.name, Meeting.Meeting_Date)\
     .order_by(Meeting.Meeting_Number, Meeting.Meeting_Date, Role.name)

    user_bookings = user_bookings_query.all()

    user_bookings_by_date = {}
    for log in user_bookings:
        date_str = log.Meeting_Date.strftime('%Y-%m-%d')
        if date_str not in user_bookings_by_date:
            user_bookings_by_date[date_str] = {
                'date_info': {
                    'meeting_number': log.Meeting_Number,
                    'short_date': log.Meeting_Date.strftime('%m/%d/%Y')
                },
                'bookings': []
            }
        user_bookings_by_date[date_str]['bookings'].append({
            'role': log.name,
            'role_key': log.name,
            'icon': next((config.get('icon', current_app.config['DEFAULT_ROLE_ICON'])
                          for config in current_app.config['ROLES'].values()
                          if config['name'] == log.name
                          ), current_app.config['DEFAULT_ROLE_ICON']),
            'session_id': log.id
        })

    return sorted(user_bookings_by_date.values(), key=lambda x: x['date_info']['meeting_number'])


def _get_completed_roles(current_user_contact_id, selected_level):
    """Fetches a user's completed roles for a given level."""
    if not current_user_contact_id or not selected_level:
        return []

    level_pattern = f"%{selected_level}%"
    today = datetime.today().date()

    try:
        completed_logs = db.session.query(
            Meeting.Meeting_Number,
            Meeting.Meeting_Date,
            Role.name
        ).select_from(SessionLog)\
         .join(SessionType, SessionLog.Type_ID == SessionType.id)\
         .join(Role, SessionType.role_id == Role.id)\
         .join(Meeting, SessionLog.Meeting_Number == Meeting.Meeting_Number)\
         .filter(SessionLog.Owner_ID == current_user_contact_id)\
         .filter(Role.name.isnot(None), Role.name != '', Role.name != 'Prepared Speaker')\
         .filter(SessionLog.current_path_level.like(level_pattern))\
         .filter(Meeting.Meeting_Date < today)\
         .distinct()\
         .order_by(Meeting.Meeting_Number.desc(), Role.name.asc()).all()

        return [{
            'role': role_name,
            'meeting_number': meeting_num,
            'date': meeting_date.strftime('%Y-%m-%d'),
            'icon': next((config.get('icon', current_app.config['DEFAULT_ROLE_ICON'])
                for config in current_app.config['ROLES'].values()
                if config['name'] == role_name
                          ), current_app.config['DEFAULT_ROLE_ICON'])
        } for meeting_num, meeting_date, role_name in completed_logs]

    except Exception as e:
        current_app.logger.error(f"Error fetching completed roles: {e}")
        return []


def _get_best_award_ids(selected_meeting):
    """Gets the set of best award IDs for a meeting."""
    if not selected_meeting:
        return set()
    return {
        award_id for award_id in [
            selected_meeting.best_table_topic_id,
            selected_meeting.best_evaluator_id,
            selected_meeting.best_speaker_id,
            selected_meeting.best_role_taker_id
        ] if award_id
    }


def _get_booking_page_context(selected_meeting_number, user, user_role, current_user_contact_id):
    """Gathers all context needed for the booking page template."""
    default_level = _get_default_level(user)
    selected_level = request.args.get('level', default=default_level, type=int)

    upcoming_meetings, default_meeting_num = _get_meetings(user_role)

    if not selected_meeting_number:
        selected_meeting_number = default_meeting_num or (
            upcoming_meetings[0][0] if upcoming_meetings else None)

    context = {
        'roles': [], 'upcoming_meetings': upcoming_meetings,
        'selected_meeting_number': selected_meeting_number,
        'user_bookings_by_date': [], 'contacts': [], 'completed_roles': [],
        'selected_level': selected_level, 'selected_meeting': None,
        'is_admin_view': is_authorized(user_role, 'BOOKING_ASSIGN_ALL'),
        'current_user_contact_id': current_user_contact_id,
        'user_role': user_role,
        'best_award_ids': set()
    }

    if not selected_meeting_number:
        return context

    selected_meeting = Meeting.query.filter_by(
        Meeting_Number=selected_meeting_number).first()
    context['selected_meeting'] = selected_meeting

    is_past_meeting = False
    if selected_meeting and selected_meeting.Meeting_Date:
        is_past_meeting = selected_meeting.Meeting_Date < datetime.today().date()
    context['is_past_meeting'] = is_past_meeting

    context['roles'] = _get_roles_for_meeting(
        selected_meeting_number, user_role, current_user_contact_id, selected_meeting, is_past_meeting)

    context['user_bookings_by_date'] = _get_user_bookings(
        current_user_contact_id)
    context['completed_roles'] = _get_completed_roles(
        current_user_contact_id, selected_level)

    if context['is_admin_view']:
        context['contacts'] = Contact.query.order_by(Contact.Name).all()

    context['best_award_ids'] = _get_best_award_ids(selected_meeting)

    return context


@booking_bp.route('/booking', defaults={'selected_meeting_number': None}, methods=['GET'])
@booking_bp.route('/booking/<int:selected_meeting_number>', methods=['GET'])
def booking(selected_meeting_number):
    user, user_role, current_user_contact_id = _get_user_info()
    context = _get_booking_page_context(
        selected_meeting_number, user, user_role, current_user_contact_id)
    return render_template('booking.html', **context)


@booking_bp.route('/booking/book', methods=['POST'])
@login_required
def book_or_assign_role():
    data = request.get_json()
    session_id = data.get('session_id')
    action = data.get('action')

    user, user_role, current_user_contact_id = _get_user_info()

    log = SessionLog.query.get(session_id)
    if not log:
        return jsonify(success=False, message="Session not found."), 404

    session_type = SessionType.query.get(log.Type_ID)
    logical_role_key = session_type.role.name if session_type and session_type.role else None

    if not logical_role_key:
        return jsonify(success=False, message="Could not determine the role key."), 400

    if action == 'join_waitlist':
        sessions_to_waitlist = []
        if logical_role_key in current_app.config['UNIQUE_ENTRY_ROLES']:
            sessions_to_waitlist = [log]
        else:
            # For non-unique roles, find all session logs for this role in the meeting
            sessions_to_waitlist = SessionLog.query.join(SessionType).join(Role, SessionType.role_id == Role.id)\
                .filter(SessionLog.Meeting_Number == log.Meeting_Number)\
                .filter(Role.name == logical_role_key).all()

        for session_log in sessions_to_waitlist:
            existing_waitlist = Waitlist.query.filter_by(
                session_log_id=session_log.id, contact_id=current_user_contact_id).first()
            if not existing_waitlist:
                new_waitlist_entry = Waitlist(
                    session_log_id=session_log.id,
                    contact_id=current_user_contact_id,
                    timestamp=datetime.utcnow()
                )
                db.session.add(new_waitlist_entry)

        db.session.commit()
        return jsonify(success=True)
    elif action == 'book':
        # Check if the role needs approval
        role_needs_approval = session_type.role.needs_approval if session_type and session_type.role else False

        if role_needs_approval:
            # For roles that need approval, always put user on waitlist
            sessions_to_waitlist = []
            if logical_role_key in current_app.config['UNIQUE_ENTRY_ROLES']:
                sessions_to_waitlist = [log]
            else:
                # For non-unique roles, find all session logs for this role in the meeting
                sessions_to_waitlist = SessionLog.query.join(SessionType).join(Role, SessionType.role_id == Role.id)\
                    .filter(SessionLog.Meeting_Number == log.Meeting_Number)\
                    .filter(Role.name == logical_role_key).all()

            for session_log in sessions_to_waitlist:
                existing_waitlist = Waitlist.query.filter_by(
                    session_log_id=session_log.id, contact_id=current_user_contact_id).first()
                if not existing_waitlist:
                    new_waitlist_entry = Waitlist(
                        session_log_id=session_log.id,
                        contact_id=current_user_contact_id,
                        timestamp=datetime.utcnow()
                    )
                    db.session.add(new_waitlist_entry)

            db.session.commit()
            return jsonify(success=True, message="You have been added to the waitlist for this role. The booking requires approval.")
        elif log.Owner_ID is not None:
            return jsonify(success=False, message="This role is already booked.")
        else:
            owner_id_to_set = current_user_contact_id
    elif action == 'cancel':
        # Check if the role needs approval
        role_needs_approval = session_type.role.needs_approval if session_type and session_type.role else False

        if role_needs_approval:
            # For roles that need approval, do not automatically promote from waitlist
            owner_id_to_set = None
        else:
            # Original logic for roles that don't need approval
            waitlist_entry = Waitlist.query.filter_by(
                session_log_id=session_id).order_by(Waitlist.timestamp).first()
            if waitlist_entry:
                # This user is being promoted.
                owner_id_to_set = waitlist_entry.contact_id

                # Now, remove this user from the waitlist of ALL sessions for this role in this meeting.
                sessions_to_leave = SessionLog.query.join(SessionType).join(Role, SessionType.role_id == Role.id)\
                    .filter(SessionLog.Meeting_Number == log.Meeting_Number)\
                    .filter(Role.name == logical_role_key).all()

                for session_log in sessions_to_leave:
                    Waitlist.query.filter_by(
                        session_log_id=session_log.id, contact_id=owner_id_to_set).delete(synchronize_session=False)

            else:
                owner_id_to_set = None
    elif action == 'leave_waitlist':
        sessions_to_leave = []
        if logical_role_key in current_app.config['UNIQUE_ENTRY_ROLES']:
            sessions_to_leave.append(log)
        else:
            sessions_to_leave = SessionLog.query.join(SessionType).join(Role, SessionType.role_id == Role.id)\
                .filter(SessionLog.Meeting_Number == log.Meeting_Number)\
                .filter(Role.name == logical_role_key).all()

        for session_log in sessions_to_leave:
            waitlist_entry = Waitlist.query.filter_by(
                session_log_id=session_log.id, contact_id=current_user_contact_id).first()
            if waitlist_entry:
                db.session.delete(waitlist_entry)

        db.session.commit()
        return jsonify(success=True, message="You have been removed from the waitlist.")
    elif action == 'assign' and is_authorized(user_role, 'BOOKING_ASSIGN_ALL'):
        contact_id = data.get('contact_id', '0')
        owner_id_to_set = int(contact_id) if contact_id != '0' else None

        # If assigning a specific user (not unassigning), remove that user from the waitlist
        if owner_id_to_set:
            # Remove this user from the waitlist of ALL sessions for this role in this meeting.
            sessions_to_leave = SessionLog.query.join(SessionType).join(Role, SessionType.role_id == Role.id)\
                .filter(SessionLog.Meeting_Number == log.Meeting_Number)\
                .filter(Role.name == logical_role_key).all()

            for session_log in sessions_to_leave:
                Waitlist.query.filter_by(
                    session_log_id=session_log.id, contact_id=owner_id_to_set).delete(synchronize_session=False)

    elif action == 'approve_waitlist' and is_authorized(user_role, 'BOOKING_ASSIGN_ALL'):
        # Get the top person from the waitlist for this specific session_id
        waitlist_entry = Waitlist.query.filter_by(
            session_log_id=session_id).order_by(Waitlist.timestamp).first()

        if not waitlist_entry:
            return jsonify(success=False, message="No one is on the waitlist to approve."), 404

        owner_id_to_set = waitlist_entry.contact_id

        # Remove the approved user from the waitlist of ALL sessions for this role in this meeting.
        sessions_to_leave = SessionLog.query.join(SessionType).join(Role, SessionType.role_id == Role.id)\
            .filter(SessionLog.Meeting_Number == log.Meeting_Number)\
            .filter(Role.name == logical_role_key).all()

        for session_log in sessions_to_leave:
            Waitlist.query.filter_by(
                session_log_id=session_log.id, contact_id=owner_id_to_set).delete(synchronize_session=False)

    else:
        return jsonify(success=False, message="Invalid action or permissions."), 403

    owner_contact = Contact.query.get(
        owner_id_to_set) if owner_id_to_set else None
    new_path_level = derive_current_path_level(
        log, owner_contact) if owner_contact else None

    new_designation = derive_designation(owner_contact)

    non_distinct_roles = current_app.config['UNIQUE_ENTRY_ROLES'] + \
        ([current_app.config['ROLES']['TOPICS_SPEAKER']['name']]
         if is_authorized(user_role, 'BOOKING_ASSIGN_ALL') else [])

    if logical_role_key in non_distinct_roles:
        sessions_to_update = [log]
    else:
        sessions_to_update = SessionLog.query.join(SessionType).join(Role, SessionType.role_id == Role.id)\
            .filter(SessionLog.Meeting_Number == log.Meeting_Number)\
            .filter(Role.name == logical_role_key).all()

    for session_log in sessions_to_update:
        # Re-fetch owner_contact and derive path/designation inside the loop if needed,
        # but for simplicity, we can do it once if the owner is the same for all.
        owner_contact = Contact.query.get(
            owner_id_to_set) if owner_id_to_set else None
        new_path_level = derive_current_path_level(
            session_log, owner_contact) if owner_contact else None
        new_designation = derive_designation(owner_contact)

        session_log.Owner_ID = owner_id_to_set
        session_log.current_path_level = new_path_level
        session_log.Designation = new_designation

    try:
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during booking/assignment: {e}")
        return jsonify(success=False, message="An internal error occurred."), 500


@booking_bp.route('/booking/vote', methods=['POST'])
@login_required
def vote_for_award():
    if not is_authorized(session.get('user_role'), 'BOOKING_ASSIGN_ALL'):
        return jsonify(success=False, message="Permission denied."), 403

    data = request.get_json()
    meeting_number = data.get('meeting_number')
    contact_id = data.get('contact_id')
    award_category = data.get('award_category')

    if not all([meeting_number, contact_id, award_category]):
        return jsonify(success=False, message="Missing data."), 400

    meeting = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
    if not meeting:
        return jsonify(success=False, message="Meeting not found."), 404

    award_attr = f"best_{award_category.replace('-', '_')}_id"

    if not hasattr(meeting, award_attr):
        current_app.logger.error(
            f"Meeting object does not have attribute: {award_attr}")
        return jsonify(success=False, message="Invalid award category."), 400

    try:
        current_winner = getattr(meeting, award_attr)
        new_winner_id = None
        if current_winner == contact_id:
            setattr(meeting, award_attr, None)
        else:
            setattr(meeting, award_attr, contact_id)
            new_winner_id = contact_id

        db.session.commit()
        return jsonify(success=True, new_winner_id=new_winner_id, award_category=award_category)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error voting for award: {e}")
        return jsonify(success=False, message="An internal error occurred."), 500
