# vpemaster/booking_routes.py

from .auth.utils import login_required, is_authorized
from flask import Blueprint, render_template, request, session, jsonify, current_app
from .models import SessionLog, SessionType, Contact, Meeting, User, LevelRole, Waitlist, Role, Vote
from . import db
from datetime import datetime
import re
import secrets
from sqlalchemy import or_
from .utils import derive_current_path_level, derive_credentials
from .utils import get_meetings_by_status

booking_bp = Blueprint('booking_bp', __name__)


def _fetch_session_logs(selected_meeting_number, user_role):
    """Fetches session logs for a given meeting, filtering by user role."""
    # Fetch the full SessionLog objects to ensure all data is available for consolidation.
    query = db.session.query(SessionLog)\
        .join(SessionType, SessionLog.Type_ID == SessionType.id)\
        .join(Role, SessionType.role_id == Role.id)\
        .filter(SessionLog.Meeting_Number == selected_meeting_number)\
        .filter(Role.name != '', Role.name.isnot(None))

    if not is_authorized(user_role, 'BOOKING_ASSIGN_ALL'):
        query = query.filter(Role.type != 'officer')

    return query.all()


def _consolidate_roles(session_logs, is_admin_booker):
    """Consolidates session logs into a dictionary of roles."""
    roles_dict = {}

    # Per user's definition: is_distinct=True means the role is a single logical entity for the meeting.
    # These are the roles that need to be grouped by name.
    distinct_role_records = Role.query.filter_by(is_distinct=True).all()
    roles_to_group = {role.name for role in distinct_role_records}

    # First pass: Group session logs by their logical key
    for log in session_logs:
        # The log is now a full SessionLog object, so we access relations directly.
        role_key = log.session_type.role.name.strip(
        ) if log.session_type and log.session_type.role else ""
        if not role_key:
            continue

        if role_key in roles_to_group:
            dict_key = role_key
        else:
            dict_key = f"{role_key}_{log.id}"

        if dict_key not in roles_dict:
            # Initialize the entry for this role group
            roles_dict[dict_key] = {
                'role': role_key,
                'role_key': role_key,
                'owner_id': None,
                'owner_name': None,
                'session_ids': [],
                'type_id': log.Type_ID,
                'speaker_name': log.Session_Title.strip() if role_key == "Individual Evaluator" and log.Session_Title else None,
                'waitlist': [],
                'logs': []  # Store the full log objects
            }

        roles_dict[dict_key]['session_ids'].append(log.id)
        roles_dict[dict_key]['logs'].append(log)

    # Second pass: Determine the owner and consolidate waitlists for each group
    for dict_key, role_data in roles_dict.items():
        # Find the first log in the group that has an owner.
        owner_log = next(
            (log for log in role_data['logs'] if log.Owner_ID), None)

        if owner_log:
            role_data['owner_id'] = owner_log.Owner_ID
            # Access owner name via relationship
            role_data['owner_name'] = owner_log.owner.Name if owner_log.owner else None

        # Consolidate waitlists from all logs in the group, avoiding duplicates.
        seen_waitlist_ids = set()
        for log in role_data['logs']:
            for waitlist_entry in log.waitlists:
                if waitlist_entry.contact_id not in seen_waitlist_ids:
                    role_data['waitlist'].append(
                        {'name': waitlist_entry.contact.Name, 'id': waitlist_entry.contact_id})
                    seen_waitlist_ids.add(waitlist_entry.contact_id)
        del role_data['logs']  # Clean up the temporary logs list
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
        role_data['needs_approval'] = role_obj.needs_approval if role_obj else False

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
    all_meetings_tuples = get_meetings_by_status(
        limit_past=5, columns=[Meeting.Meeting_Number, Meeting.Meeting_Date])

    soonest_upcoming_meeting = db.session.query(Meeting.Meeting_Number)\
        .filter(Meeting.status == 'not started')\
        .order_by(Meeting.Meeting_Number.asc())\
        .first()
    default_meeting_num = soonest_upcoming_meeting[0] if soonest_upcoming_meeting else None

    return all_meetings_tuples, default_meeting_num


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

    is_past_meeting = selected_meeting.status == 'finished' if selected_meeting else False

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
        role_is_distinct = session_type.role.is_distinct if session_type and session_type.role else False
        session_ids_to_waitlist = _get_all_session_ids_for_role(
            log, logical_role_key) if role_is_distinct else [session_id]

        for s_id in session_ids_to_waitlist:
            existing_waitlist = Waitlist.query.filter_by(
                session_log_id=s_id, contact_id=current_user_contact_id).first()
            if not existing_waitlist:
                new_waitlist_entry = Waitlist(
                    session_log_id=s_id,
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
            role_is_distinct = session_type.role.is_distinct if session_type and session_type.role else False
            session_ids_to_waitlist = _get_all_session_ids_for_role(
                log, logical_role_key) if role_is_distinct else [session_id]

            for s_id in session_ids_to_waitlist:
                existing_waitlist = Waitlist.query.filter_by(
                    session_log_id=s_id, contact_id=current_user_contact_id).first()
                if not existing_waitlist:
                    new_waitlist_entry = Waitlist(
                        session_log_id=s_id,
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
                db.session.delete(waitlist_entry)

            else:
                owner_id_to_set = None
    elif action == 'leave_waitlist':
        waitlist_entry = Waitlist.query.filter_by(
            session_log_id=session_id, contact_id=current_user_contact_id).first()
        if waitlist_entry:
            db.session.delete(waitlist_entry)

        db.session.commit()
        return jsonify(success=True, message="You have been removed from the waitlist.")
    elif action == 'assign' and is_authorized(user_role, 'BOOKING_ASSIGN_ALL'):
        contact_id = data.get('contact_id', '0')
        owner_id_to_set = int(contact_id) if contact_id != '0' else None

        # If assigning a specific user (not unassigning), remove that user from the waitlist
        if owner_id_to_set:
            # If assigning a user, remove them from the waitlist of all related sessions for a distinct role.
            role_is_distinct = session_type.role.is_distinct if session_type and session_type.role else False
            if role_is_distinct:
                sessions_to_clear_waitlist = _get_all_session_ids_for_role(
                    log, logical_role_key)
                Waitlist.query.filter(Waitlist.session_log_id.in_(
                    sessions_to_clear_waitlist), Waitlist.contact_id == owner_id_to_set).delete(synchronize_session=False)
            else:
                Waitlist.query.filter_by(session_log_id=session_id, contact_id=owner_id_to_set).delete(
                    synchronize_session=False)

    elif action == 'approve_waitlist' and is_authorized(user_role, 'BOOKING_ASSIGN_ALL'):
        # Get the top person from the waitlist for this specific session_id
        waitlist_entry = Waitlist.query.filter_by(
            session_log_id=session_id).order_by(Waitlist.timestamp).first()

        if not waitlist_entry:
            return jsonify(success=False, message="No one is on the waitlist to approve."), 404

        owner_id_to_set = waitlist_entry.contact_id
        db.session.delete(waitlist_entry)

    else:
        return jsonify(success=False, message="Invalid action or permissions."), 403

    try:
        owner_contact = Contact.query.get(
            owner_id_to_set) if owner_id_to_set else None
        new_credentials = derive_credentials(owner_contact)

        # Check if the role is distinct (should only have one entry per meeting)
        role_is_distinct = session_type.role.is_distinct if session_type and session_type.role else False

        if role_is_distinct:
            sessions_to_update = SessionLog.query.join(SessionType).join(Role, SessionType.role_id == Role.id)\
                .filter(SessionLog.Meeting_Number == log.Meeting_Number)\
                .filter(Role.name == logical_role_key).all()
        else:  # For non-distinct roles, only update the specific session that was clicked
            sessions_to_update = [log]

        for session_log in sessions_to_update:
            new_path_level = derive_current_path_level(
                session_log, owner_contact) if owner_contact else None

            session_log.Owner_ID = owner_id_to_set
            session_log.current_path_level = new_path_level
            session_log.credentials = new_credentials

        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during booking/assignment: {e}")
        return jsonify(success=False, message="An internal error occurred."), 500


def _get_all_session_ids_for_role(log, logical_role_key):
    """Helper to get all session_log IDs for a given logical role in a meeting."""
    all_logs_for_role = SessionLog.query.join(SessionType).join(Role)\
        .filter(SessionLog.Meeting_Number == log.Meeting_Number)\
        .filter(Role.name == logical_role_key).all()
    return [l.id for l in all_logs_for_role]


@booking_bp.route('/booking/vote', methods=['POST'])
def vote_for_award():
    data = request.get_json()
    meeting_number = data.get('meeting_number')
    contact_id = data.get('contact_id')
    award_category = data.get('award_category')

    if not all([meeting_number, contact_id, award_category]):
        return jsonify(success=False, message="Missing data."), 400

    meeting = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
    if not meeting:
        return jsonify(success=False, message="Meeting not found."), 404

    if meeting.status != 'running':
        return jsonify(success=False, message="Voting is not active for this meeting."), 403

    # 1. Determine voter identity
    if 'user_id' in session:
        voter_identifier = f"user_{session['user_id']}"
    else:
        if 'voter_token' not in session:
            session['voter_token'] = secrets.token_hex(16)
        voter_identifier = session['voter_token']
    
    # 2. Check for an existing vote from this identifier for this category
    existing_vote = Vote.query.filter_by(
        meeting_number=meeting_number,
        voter_identifier=voter_identifier,
        award_category=award_category
    ).first()

    your_vote_id = None

    try:
        if existing_vote:
            if existing_vote.contact_id == contact_id:
                # User clicked the same person again, so cancel the vote
                db.session.delete(existing_vote)
                your_vote_id = None
            else:
                # User is changing their vote to a new person
                existing_vote.contact_id = contact_id
                your_vote_id = contact_id
        else:
            # New vote
            new_vote = Vote(
                meeting_number=meeting_number,
                voter_identifier=voter_identifier,
                award_category=award_category,
                contact_id=contact_id
            )
            db.session.add(new_vote)
            your_vote_id = contact_id

        db.session.commit()
        return jsonify(success=True, your_vote_id=your_vote_id, award_category=award_category)

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing vote: {e}")
        return jsonify(success=False, message="An internal error occurred."), 500
