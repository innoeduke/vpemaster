# vpemaster/booking_routes.py

from .auth.utils import login_required, is_authorized
from flask import Blueprint, render_template, request, session, jsonify, current_app
from .models import SessionLog, SessionType, Contact, Meeting, Pathway, PathwayProject, Waitlist, Role
from . import db
from datetime import datetime
from sqlalchemy import func
from .utils import derive_credentials
from .constants import SessionTypeID
from flask_login import current_user

from .booking_voting_shared import (
    get_user_info,
    get_meetings,
    fetch_session_logs,
    consolidate_roles,
    get_best_award_ids,
    group_roles_by_category
)

booking_bp = Blueprint('booking_bp', __name__)


def _enrich_role_data_for_booking(roles_dict, selected_meeting):
    """
    Enriches role data with booking-specific information.
    
    Args:
        roles_dict: Dictionary of consolidated roles
        selected_meeting: Meeting object
    
    Returns:
        list: Enriched roles list
    """
    if not selected_meeting:
        return []

    enriched_roles = []
    for _, role_data in roles_dict.items():
        role_obj = role_data.get('role_obj')
        if not role_obj:
            role_obj = Role.query.filter_by(name=role_data['role_key']).first()

        role_data['icon'] = role_obj.icon if role_obj and role_obj.icon else "fa-question-circle"
        role_data['session_id'] = role_data['session_ids'][0]
        role_data['needs_approval'] = role_obj.needs_approval if role_obj else False
        role_data['is_member_only'] = role_obj.is_member_only if role_obj else False
        role_data['award_category'] = role_obj.award_category if role_obj else None

        enriched_roles.append(role_data)
    
    return enriched_roles


def _apply_user_filters_and_rules(roles, current_user_contact_id, selected_meeting_number):
    """Applies filtering and business rules based on user permissions."""
    if is_authorized('BOOKING_ASSIGN_ALL'):
        return roles

    # 3-Week Policy speaker rule
    if current_user.is_authenticated and current_user.contact and current_user.contact.Current_Path:
        three_meetings_ago = selected_meeting_number - 2
        recent_speaker_log = db.session.query(SessionLog.id).join(SessionType).join(Role, SessionType.role_id == Role.id)\
            .filter(SessionLog.Owner_ID == current_user_contact_id)\
            .filter(Role.name == "Prepared Speaker")\
            .filter(SessionLog.Meeting_Number.between(three_meetings_ago, selected_meeting_number)).first()

        if recent_speaker_log:
            roles = [
                r for r in roles
                if r['role_key'] != "Prepared Speaker" or (r['role_key'] == "Prepared Speaker" and r['owner_id'] == current_user_contact_id)
            ]

    return roles


def _sort_roles_for_booking(roles, current_user_contact_id, is_past_meeting):
    """Sorts roles for booking view."""
    CATEGORY_ORDER = {
        'speaker': 1,
        'evaluator': 2,
        'role-taker': 3,
        'table-topic': 4
    }
    
    def get_category_priority(role):
        cat = role.get('award_category', '') or ''
        return CATEGORY_ORDER.get(cat, 99)

    if is_past_meeting or is_authorized('BOOKING_ASSIGN_ALL'):
        roles.sort(key=lambda x: (
            get_category_priority(x),
            x.get('award_category', '') or '', 
            x['role']
        ))
    else:
        roles.sort(key=lambda x: (
            get_category_priority(x),
            0 if x['owner_id'] == current_user_contact_id else 1 if not x['owner_id'] else 2,
            x['role']
        ))
    
    return roles


def _get_roles_for_booking(selected_meeting_number, current_user_contact_id, selected_meeting, is_past_meeting):
    """Helper function to get and process roles for the booking page."""
    session_logs = fetch_session_logs(selected_meeting_number, meeting_obj=selected_meeting)
    roles_dict = consolidate_roles(session_logs)
    enriched_roles = _enrich_role_data_for_booking(roles_dict, selected_meeting)
    filtered_roles = _apply_user_filters_and_rules(
        enriched_roles, current_user_contact_id, selected_meeting_number)
    sorted_roles = _sort_roles_for_booking(
        filtered_roles, current_user_contact_id, is_past_meeting)

    # For 'not started' or 'unpublished' meetings, only show Topics Speaker to admins
    is_admin_booker = is_authorized('BOOKING_ASSIGN_ALL', meeting=selected_meeting)
    if selected_meeting.status in ['not started', 'unpublished'] and not is_admin_booker:
        sorted_roles = [
            role for role in sorted_roles
            if role['role_key'] != "Topics Speaker"
        ]

    return sorted_roles


def _get_user_bookings(current_user_contact_id):
    """Fetches and processes a user's upcoming bookings."""
    if not current_user_contact_id:
        return []

    today = datetime.today().date()
    user_bookings_query = db.session.query(
        db.func.min(SessionLog.id).label('id'),
        Role.name,
        Meeting.Meeting_Number,
        Meeting.Meeting_Date,
        Role.icon
    ).join(SessionType, SessionLog.Type_ID == SessionType.id)\
     .join(Role, SessionType.role_id == Role.id)\
     .join(Meeting, SessionLog.Meeting_Number == Meeting.Meeting_Number)\
     .filter(SessionLog.Owner_ID == current_user_contact_id)\
     .filter(Meeting.Meeting_Date >= today)\
     .filter(Role.name != '', Role.name.isnot(None))\
     .filter(Role.type != 'officer')\
     .group_by(Meeting.Meeting_Number, Role.name, Meeting.Meeting_Date, Role.icon)\
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
            'icon': log.icon or current_app.config['DEFAULT_ROLE_ICON'],
            'session_id': log.id
        })

    return sorted(user_bookings_by_date.values(), key=lambda x: x['date_info']['meeting_number'])


def _get_booking_page_context(selected_meeting_number, user, current_user_contact_id):
    """Gathers all context needed for the booking page template."""
    # Show all recent meetings in the dropdown, even if booking is closed for them
    upcoming_meetings, default_meeting_num = get_meetings(limit_past=5)

    if not selected_meeting_number:
        selected_meeting_number = default_meeting_num or (
            upcoming_meetings[0][0] if upcoming_meetings else None)

    context = {
        'roles': [],
        'upcoming_meetings': upcoming_meetings,
        'selected_meeting_number': selected_meeting_number,
        'user_bookings_by_date': [],
        'contacts': [],
        'selected_meeting': None,
        'is_admin_view': is_authorized('BOOKING_ASSIGN_ALL'),
        'current_user_contact_id': current_user_contact_id,
        'user_role': current_user.Role if current_user.is_authenticated else 'Guest',
        'best_award_ids': set()
    }

    if not selected_meeting_number:
        return context

    selected_meeting = Meeting.query.filter_by(Meeting_Number=selected_meeting_number).first()
    
    is_manager = current_user.is_authenticated and current_user.Contact_ID == selected_meeting.manager_id if selected_meeting else False
    if selected_meeting and selected_meeting.status == 'unpublished' and not (context['is_admin_view'] or (current_user.is_authenticated and current_user.is_officer) or is_manager):
        from flask import abort
        abort(403)

    context['selected_meeting'] = selected_meeting
    context['is_admin_view'] = is_authorized('BOOKING_ASSIGN_ALL', meeting=selected_meeting)

    is_past_meeting = selected_meeting.status == 'finished' if selected_meeting else False

    roles = _get_roles_for_booking(
        selected_meeting_number, current_user_contact_id, selected_meeting, is_past_meeting)
    context['roles'] = roles

    context['user_bookings_by_date'] = _get_user_bookings(current_user_contact_id)

    if context['is_admin_view']:
        context['contacts'] = Contact.query.order_by(Contact.Name).all()

    context['best_award_ids'] = get_best_award_ids(selected_meeting)
    context['sorted_role_groups'] = group_roles_by_category(roles)

    return context


@booking_bp.route('/booking', defaults={'selected_meeting_number': None}, methods=['GET'])
@booking_bp.route('/booking/<int:selected_meeting_number>', methods=['GET'])
def booking(selected_meeting_number):
    """Main booking page route."""
    user, current_user_contact_id = get_user_info()
    context = _get_booking_page_context(selected_meeting_number, user, current_user_contact_id)
    return render_template('booking.html', **context)


@booking_bp.route('/booking/book', methods=['POST'])
@login_required
def book_or_assign_role():
    """Booking and assignment endpoint."""
    data = request.get_json()
    session_id = data.get('session_id')
    action = data.get('action')

    user, current_user_contact_id = get_user_info()

    log = SessionLog.query.get(session_id)
    if not log:
        return jsonify(success=False, message="Session not found."), 404

    session_type = SessionType.query.get(log.Type_ID)
    logical_role_key = session_type.role.name if session_type and session_type.role else None

    if not logical_role_key:
        return jsonify(success=False, message="Could not determine the role key."), 400

    # Validation: Check meeting status
    meeting = Meeting.query.filter_by(Meeting_Number=log.Meeting_Number).first()
    if not meeting:
        return jsonify(success=False, message="Meeting not found."), 404

    if meeting.status == 'finished':
        return jsonify(success=False, message="Booking is closed for finished meetings."), 403

    if action == 'book':
        if meeting.status == 'running':
            if not is_authorized('BOOKING_ASSIGN_ALL', meeting=meeting):
                return jsonify(success=False, message="Booking is closed for this meeting."), 403

    if action == 'join_waitlist':
        is_distinct = session_type.role.is_distinct if session_type and session_type.role else False
        
        if is_distinct:
             session_ids_to_waitlist = [session_id]
        else:
             session_ids_to_waitlist = _get_all_session_ids_for_group(log, logical_role_key, log.Owner_ID)

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
        role_needs_approval = session_type.role.needs_approval if session_type and session_type.role else False

        if role_needs_approval:
            is_distinct = session_type.role.is_distinct if session_type and session_type.role else False
            
            if is_distinct:
                 session_ids_to_waitlist = [session_id]
            else:
                 session_ids_to_waitlist = _get_all_session_ids_for_group(log, logical_role_key, log.Owner_ID)

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
        role_needs_approval = session_type.role.needs_approval if session_type and session_type.role else False

        if role_needs_approval:
            owner_id_to_set = None
        else:
            waitlist_entry = Waitlist.query.filter_by(
                session_log_id=session_id).order_by(Waitlist.timestamp).first()
            if waitlist_entry:
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
    elif action == 'assign' and is_authorized('BOOKING_ASSIGN_ALL', meeting=meeting):
        contact_id = data.get('contact_id', '0')
        owner_id_to_set = int(contact_id) if contact_id != '0' else None

        if owner_id_to_set:
            is_distinct = session_type.role.is_distinct if session_type and session_type.role else False
            if is_distinct:
                sessions_to_clear_waitlist = [session_id]
            else:
                sessions_to_clear_waitlist = _get_all_session_ids_for_group(log, logical_role_key, log.Owner_ID)

            Waitlist.query.filter(Waitlist.session_log_id.in_(
                sessions_to_clear_waitlist), Waitlist.contact_id == owner_id_to_set).delete(synchronize_session=False)

    elif action == 'approve_waitlist' and is_authorized('BOOKING_ASSIGN_ALL', meeting=meeting):
        waitlist_entry = Waitlist.query.filter_by(
            session_log_id=session_id).order_by(Waitlist.timestamp).first()

        if not waitlist_entry:
            return jsonify(success=False, message="No one is on the waitlist to approve."), 404

        owner_id_to_set = waitlist_entry.contact_id

        is_distinct = session_type.role.is_distinct if session_type and session_type.role else False
        if is_distinct:
            sessions_to_clear_waitlist = [session_id]
        else:
            sessions_to_clear_waitlist = _get_all_session_ids_for_group(log, logical_role_key, log.Owner_ID)
            
        Waitlist.query.filter(Waitlist.session_log_id.in_(
            sessions_to_clear_waitlist), Waitlist.contact_id == owner_id_to_set).delete(synchronize_session=False)

    else:
        return jsonify(success=False, message="Invalid action or permissions."), 403

    try:
        owner_contact = Contact.query.get(owner_id_to_set) if owner_id_to_set else None
        new_credentials = derive_credentials(owner_contact)

        session_type = log.session_type
        role_obj = session_type.role
        is_distinct = role_obj.is_distinct

        if is_distinct:
            sessions_to_update = [log]
        else:
            target_role_id = role_obj.id
            target_owner_id = log.Owner_ID
            
            sessions_query = db.session.query(SessionLog)\
                .join(SessionType, SessionLog.Type_ID == SessionType.id)\
                .join(Role, SessionType.role_id == Role.id)\
                .filter(SessionLog.Meeting_Number == log.Meeting_Number)\
                .filter(Role.id == target_role_id)
            
            if target_owner_id is None:
                sessions_query = sessions_query.filter(SessionLog.Owner_ID.is_(None))
            else:
                sessions_query = sessions_query.filter(SessionLog.Owner_ID == target_owner_id)
            
            sessions_to_update = sessions_query.all()

        updated_sessions = []
        for session_log in sessions_to_update:
            new_path_level = session_log.derive_project_code(owner_contact) if owner_contact else None

            # Auto-Resolution of Project ID from Next_Project
            if owner_contact and owner_contact.Next_Project and session_log.Type_ID == SessionTypeID.PREPARED_SPEECH:
                current_path_name = owner_contact.Current_Path
                if current_path_name:
                    pathway = Pathway.query.filter_by(name=current_path_name).first()
                    if pathway and pathway.abbr:
                        if owner_contact.Next_Project.startswith(pathway.abbr):
                            code_suffix = owner_contact.Next_Project[len(pathway.abbr):]
                            
                            pp = PathwayProject.query.filter_by(
                                path_id=pathway.id,
                                code=code_suffix
                            ).first()
                            
                            if pp:
                                session_log.Project_ID = pp.project_id
                                new_path_level = owner_contact.Next_Project

            session_log.Owner_ID = owner_id_to_set
            session_log.project_code = new_path_level
            session_log.credentials = new_credentials
            
            updated_sessions.append({
                'session_id': session_log.id,
                'owner_id': owner_id_to_set,
                'owner_name': owner_contact.Name if owner_contact else None,
                'owner_avatar_url': owner_contact.Avatar_URL if owner_contact else None,
                'credentials': new_credentials
            })

        db.session.commit()
        return jsonify(success=True, updated_sessions=updated_sessions)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during booking/assignment: {e}")
        return jsonify(success=False, message="An internal error occurred."), 500


def _get_all_session_ids_for_group(log, logical_role_key, owner_id):
    """Helper to get all session_log IDs for a given group (role, owner)."""
    query = db.session.query(SessionLog).join(SessionType).join(Role)\
        .filter(SessionLog.Meeting_Number == log.Meeting_Number)\
        .filter(Role.name == logical_role_key)
        
    if owner_id:
        query = query.filter(SessionLog.Owner_ID == owner_id)
    else:
        query = query.filter(SessionLog.Owner_ID.is_(None))
        
    return [l.id for l in query.all()]
