# vpemaster/booking_routes.py

from datetime import datetime
from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
from flask_login import current_user
from flask import Blueprint, render_template, request, session, jsonify, current_app, redirect, url_for
from .club_context import get_current_club_id
from .utils import get_current_user_info, group_roles_by_category, get_meetings_by_status, derive_credentials
from .models import SessionLog, SessionType, Contact, Meeting, Waitlist, MeetingRole, OwnerMeetingRoles, ContactClub

from .services.role_service import RoleService
from . import db

booking_bp = Blueprint('booking_bp', __name__)


def _apply_user_filters_and_rules(roles, current_user_contact_id, selected_meeting_number):
    """Applies filtering and business rules based on user permissions."""
    if is_authorized(Permissions.BOOKING_ASSIGN_ALL):
        return roles

    # --- Rule: Hide roles without award category (other roles) for non-admins ---
    roles = [r for r in roles if r.get('award_category') not in ['none', None, '']]

    # 3-Week Policy speaker rule
    club_id = get_current_club_id()
    contact = current_user.get_contact(club_id) if current_user.is_authenticated else None
    
    if contact and contact.Current_Path:
        three_meetings_ago = selected_meeting_number - 2
        
        # Updated query to use OwnerMeetingRoles
        recent_speaker_log = db.session.query(SessionLog.id)\
            .join(SessionType)\
            .join(MeetingRole, SessionType.role_id == MeetingRole.id)\
            .join(Meeting, SessionLog.Meeting_Number == Meeting.Meeting_Number)\
            .filter(
                db.exists().where(
                    db.and_(
                        OwnerMeetingRoles.contact_id == current_user_contact_id,
                        OwnerMeetingRoles.meeting_id == Meeting.id,
                        OwnerMeetingRoles.role_id == MeetingRole.id,
                        db.or_(
                            OwnerMeetingRoles.session_log_id == SessionLog.id,
                            OwnerMeetingRoles.session_log_id.is_(None)
                        )
                    )
                )
            )\
            .filter(MeetingRole.name == "Prepared Speaker")\
            .filter(SessionLog.Meeting_Number.between(three_meetings_ago, selected_meeting_number)).first()

        if recent_speaker_log:
            roles = [
                r for r in roles
                if r['role'] != "Prepared Speaker" or (r['role'] == "Prepared Speaker" and r['owner_id'] == current_user_contact_id)
            ]

    
    # --- Rule: Hide "Topics Speaker" for non-admins ---
    # These are usually assigned ad-hoc during the meeting
    roles = [r for r in roles if r['role'] != "Topics Speaker"]

    # --- Rule: Hide duplicate role types if user already has one ---
    # 1. Identify roles the user currently owns in this meeting
    owned_roles = {r['role'] for r in roles if r['owner_id'] == current_user_contact_id}
    
    # 2. Filter logic
    filtered_roles = []
    
    # Group by role key to check for duplicates
    # Actually, we can just iterate.
    # Logic: 
    # - If I own a role of type 'X' (e.g. 'Prepared Speaker'): 
    #     - I should see ONLY the specific slot I own.
    #     - I should NOT see other available slots of type 'X'.
    # - If I do NOT own a role of type 'X':
    #     - I should see all available slots of type 'X'. 
    #     - (Wait, user requested "hide the other roles of the same type if available" implies if I have one, hide others. 
    #      What if I don't have one? Should I see all 3 speakers? Usually yes, to pick a slot.)
    
    for r in roles:
        role_label = r['role']
        owner_id = r['owner_id']
        has_single_owner = r.get('has_single_owner', True)
        
        # Contextual population for shared roles
        if not has_single_owner and 'all_owners' in r:
            all_owner_ids = [o['id'] for o in r['all_owners']]
            if current_user_contact_id in all_owner_ids:
                # User is one of the owners, show as owner for their view (to show Cancel)
                r['owner_id'] = current_user_contact_id
                # Find their owner data for display
                for o in r['all_owners']:
                    if o['id'] == current_user_contact_id:
                        r['owner_name'] = o['name']
                        r['owner_avatar_url'] = o['avatar_url']
                        break
            else:
                # Not an owner, show as available
                r['owner_id'] = None
            
            # Update owner_id variable for the filtering logic below
            owner_id = r['owner_id']

        if role_label in owned_roles:
            # User has a role of this type. Only show their own.
            if owner_id == current_user_contact_id:
                filtered_roles.append(r)
        else:
            # User does not have this role type. Show all (available or taken by others).
            filtered_roles.append(r)
            
    roles = filtered_roles

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

    if is_past_meeting or is_authorized(Permissions.BOOKING_ASSIGN_ALL):
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
    club_id = get_current_club_id()
    
    # Use RoleService to get consolidated roles
    roles = RoleService.get_meeting_roles(selected_meeting_number, club_id)
    
    # Apply user-specific filters and rules
    filtered_roles = _apply_user_filters_and_rules(
        roles, current_user_contact_id, selected_meeting_number)
    sorted_roles = _sort_roles_for_booking(
        filtered_roles, current_user_contact_id, is_past_meeting)

    # For 'not started' or 'unpublished' meetings, only show Topics Speaker to admins
    is_admin_booker = is_authorized(Permissions.BOOKING_ASSIGN_ALL, meeting=selected_meeting)
    if selected_meeting.status in ['not started', 'unpublished'] and not is_admin_booker:
        sorted_roles = [
            role for role in sorted_roles
            if role['role'] != "Topics Speaker"
        ]

    return sorted_roles


def _get_user_bookings(current_user_contact_id):
    """Fetches and processes a user's upcoming bookings."""
    if not current_user_contact_id:
        return []

    today = datetime.today().date()
    # Updated query to use OwnerMeetingRoles for filtering
    user_bookings_query = db.session.query(
        db.func.min(SessionLog.id).label('id'),
        MeetingRole.name,
        Meeting.Meeting_Number,
        Meeting.Meeting_Date,
        MeetingRole.icon
    ).join(SessionType, SessionLog.Type_ID == SessionType.id)\
     .join(MeetingRole, SessionType.role_id == MeetingRole.id)\
     .join(Meeting, SessionLog.Meeting_Number == Meeting.Meeting_Number)\
     .filter(
         db.exists().where(
            db.and_(
                OwnerMeetingRoles.contact_id == current_user_contact_id,
                OwnerMeetingRoles.meeting_id == Meeting.id,
                OwnerMeetingRoles.role_id == MeetingRole.id,
                db.or_(
                    OwnerMeetingRoles.session_log_id == SessionLog.id,
                    OwnerMeetingRoles.session_log_id.is_(None)
                )
            )
         )
     )\
     .filter(Meeting.Meeting_Date >= today)\
     .filter(MeetingRole.name != '', MeetingRole.name.isnot(None))\
     .filter(MeetingRole.type != 'officer')\
     .group_by(Meeting.Meeting_Number, MeetingRole.name, Meeting.Meeting_Date, MeetingRole.icon)\
     .order_by(Meeting.Meeting_Number, Meeting.Meeting_Date, MeetingRole.name)

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
            'icon': log.icon or current_app.config['DEFAULT_ROLE_ICON'],
            'session_id': log.id
        })

    return sorted(user_bookings_by_date.values(), key=lambda x: x['date_info']['meeting_number'])


def _get_booking_page_context(selected_meeting_number, user, current_user_contact_id):
    """Gathers all context needed for the booking page template."""
    # Show all recent meetings in the dropdown, even if booking is closed for them
    is_guest = (user.primary_role_name == 'Guest') if user else True
    limit_past = 8 if is_guest else None
    
    upcoming_meetings, default_meeting_num = get_meetings_by_status(
        limit_past=limit_past, columns=[Meeting.Meeting_Number, Meeting.Meeting_Date, Meeting.status])

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
        'is_admin_view': is_authorized(Permissions.BOOKING_ASSIGN_ALL),
        'current_user_contact_id': current_user_contact_id,
        'user_role': user.primary_role_name if user else 'Guest',
        'best_award_ids': set()
    }

    if not selected_meeting_number:
        return context

    club_id = get_current_club_id()
    selected_meeting = Meeting.query.filter_by(Meeting_Number=selected_meeting_number)
    if club_id:
        selected_meeting = selected_meeting.filter(Meeting.club_id == club_id)
    selected_meeting = selected_meeting.first()
    
    contact = user.get_contact(club_id) if (user and selected_meeting) else None
    is_manager = (contact and contact.id == selected_meeting.manager_id) if selected_meeting else False
    
    # 1. Guests can ONLY access 'running' meetings
    if not user:
        if selected_meeting.status != 'running':
            context['redirect_to_not_started'] = True
            return context

    # 2. Unpublished check
    if selected_meeting and selected_meeting.status == 'unpublished' and not (is_authorized(Permissions.VOTING_VIEW_RESULTS, meeting=selected_meeting)):
        context['redirect_to_not_started'] = True
        return context

    context['selected_meeting'] = selected_meeting
    context['is_admin_view'] = is_authorized(Permissions.BOOKING_ASSIGN_ALL, meeting=selected_meeting)

    # 3. Finished check for guests
    if selected_meeting and selected_meeting.status == 'finished':
        is_guest = (user.primary_role_name == 'Guest') if user else True
        if is_guest:
             context['redirect_to_not_started'] = True
             return context

    is_past_meeting = selected_meeting.status == 'finished' if selected_meeting else False

    roles = _get_roles_for_booking(
        selected_meeting_number, current_user_contact_id, selected_meeting, is_past_meeting)
    context['roles'] = roles

    context['user_bookings_by_date'] = _get_user_bookings(current_user_contact_id)

    if context['is_admin_view']:
        context['contacts'] = Contact.query.join(ContactClub).filter(ContactClub.club_id == club_id).order_by(Contact.Name).all()

    context['best_award_ids'] = selected_meeting.get_best_award_ids() if selected_meeting else set()
    context['sorted_role_groups'] = group_roles_by_category(roles)

    return context


@booking_bp.route('/booking', defaults={'selected_meeting_number': None}, methods=['GET'])
@booking_bp.route('/booking/<int:selected_meeting_number>', methods=['GET'])
@login_required
def booking(selected_meeting_number):
    """Main booking page route."""
    user, current_user_contact_id = get_current_user_info()
    context = _get_booking_page_context(selected_meeting_number, user, current_user_contact_id)
    
    if context.get('redirect_to_not_started'):
        meeting_num = context.get('selected_meeting_number') or selected_meeting_number
        return redirect(url_for('agenda_bp.meeting_notice', meeting_number=meeting_num))
        
    return render_template('booking.html', **context)


@booking_bp.route('/booking/book', methods=['POST'])
@login_required
def book_or_assign_role():
    """Booking and assignment endpoint."""
    data = request.get_json()
    session_id = data.get('session_id')
    action = data.get('action')

    user, current_user_contact_id = get_current_user_info()

    log = db.session.get(SessionLog, session_id)
    if not log:
        return jsonify(success=False, message="Session not found."), 404

    session_type = db.session.get(SessionType, log.Type_ID)
    logical_role = session_type.role.name if session_type and session_type.role else None

    if not logical_role:
        return jsonify(success=False, message="Could not determine the role."), 400

    # Validation: Check meeting status
    club_id = get_current_club_id()
    meeting_query = Meeting.query.filter_by(Meeting_Number=log.Meeting_Number)
    if club_id:
        meeting_query = meeting_query.filter(Meeting.club_id == club_id)
    meeting = meeting_query.first()
    if not meeting:
        return jsonify(success=False, message="Meeting not found."), 404

    if meeting.status == 'finished':
        return jsonify(success=False, message="Booking is closed for finished meetings."), 403

    try:
        if action == 'book':
            # Validation: Block booking for roles without award category if not admin
            if session_type.role and session_type.role.award_category in ['none', None, ''] and not is_authorized(Permissions.BOOKING_ASSIGN_ALL, meeting=meeting):
                return jsonify(success=False, message="This role is not available for booking."), 403

            success, msg = RoleService.book_meeting_role(log, current_user_contact_id)
            if not success:
                return jsonify(success=False, message=msg), 200 # Using 200 for internal logic warnings as per legacy
            return jsonify(success=True, message=msg)

        elif action == 'cancel':
            # Cancel for self
            success, msg = RoleService.cancel_meeting_role(log, current_user_contact_id)
            return jsonify(success=success, message=msg)

        elif action == 'join_waitlist':
            success, msg = RoleService.join_waitlist(log, current_user_contact_id)
            return jsonify(success=success, message=msg)

        elif action == 'leave_waitlist':
            success, msg = RoleService.leave_waitlist(log, current_user_contact_id)
            return jsonify(success=success, message=msg)

        # Admin Actions
        elif action == 'remove_owner' and is_authorized(Permissions.BOOKING_ASSIGN_ALL, meeting=meeting):
            # Remove a specific owner from a shared role
            owner_id_to_remove = data.get('contact_id')
            try:
                owner_id_int = int(owner_id_to_remove)
            except (ValueError, TypeError):
                return jsonify(success=False, message="Invalid owner ID"), 400
            
            # Get current owners and remove the specified one
            current_owner_ids = [o.id for o in log.owners]
            if owner_id_int not in current_owner_ids:
                return jsonify(success=False, message="Owner not found"), 404
            
            new_owner_list = [oid for oid in current_owner_ids if oid != owner_id_int]
            RoleService.assign_meeting_role(log, new_owner_list if new_owner_list else None, is_admin=True)
            db.session.commit()
            return jsonify(success=True, message="Owner removed")

        elif action == 'assign' and is_authorized(Permissions.BOOKING_ASSIGN_ALL, meeting=meeting):
            contact_id = data.get('contact_id', '0')
            previous_contact_id = data.get('previous_contact_id')
            
            try:
                contact_id_int = int(contact_id)
                owner_id_to_set = contact_id_int if contact_id_int != 0 else None
            except (ValueError, TypeError):
                owner_id_to_set = None
            
            try:
                previous_contact_id_int = int(previous_contact_id) if previous_contact_id else None
            except (ValueError, TypeError):
                previous_contact_id_int = None
            
            # Use Assign with replace logic for shared roles
            updated_logs = RoleService.assign_meeting_role(
                log, 
                owner_id_to_set, 
                is_admin=True, 
                replace_contact_id=previous_contact_id_int
            )
            
            updated_sessions = []
            for session_log in updated_logs:
                contact = session_log.owner # Using the new property
                updated_sessions.append({
                    'session_id': session_log.id,
                    'owner_id': contact.id if contact else None,
                    'owner_name': contact.Name if contact else None,
                    'owner_avatar_url': contact.Avatar_URL if contact else None,
                    'credentials': derive_credentials(contact) if contact else ''
                })
            
            db.session.commit()
            return jsonify(success=True, updated_sessions=updated_sessions)

        elif action == 'approve_waitlist' and is_authorized(Permissions.BOOKING_ASSIGN_ALL, meeting=meeting):
            success, msg = RoleService.approve_waitlist(log)
            if not success:
                 return jsonify(success=False, message=msg), 404
            
            # For approve, we also need to return updated session info because the UI updates to show the new owner
            updated_sessions = []
            # We need to know which logs were updated. RoleService.approve_waitlist calls assign_meeting_role internally
            # but doesn't return the logs in current implementation of approve_waitlist.
            # Let's just manually construct the response for THIS log since distinct/grouped roles logic
            # means other logs might have updated too.
            # Ideally approve_waitlist should return list of updated logs?
            # For now, let's fetch related logs explicitly or rely on current log.
            
            # Helper to get related logs (since we removed the private helper from here, we might need a public one or just trust this log)
            # If it's a grouped role, others were updated.
            # Let's perform a re-query for this role type in this meeting to be safe, OR just return this one 
            # and let the frontend be slightly out of sync if it displayed multiple slots?
            # Actually, frontend usually reloads or updates specific DOM elements.
            
            # Better approach: 
            # In RoleService.approve_waitlist, I can make it return the updated logs. 
            # But I can't change that file in this tool call.
            # I'll rely on fetching 'log' and if it's not distinct, fetching others.
            
            # Re-query
            sessions_to_report = [log]
            if session_type.role and not session_type.role.has_single_owner:
                 sessions_to_report = SessionLog.query.filter_by(Meeting_Number=log.Meeting_Number, Type_ID=log.Type_ID).all()
            
            for session_log in sessions_to_report:
                 contact = session_log.owner
                 updated_sessions.append({
                    'session_id': session_log.id,
                    'owner_id': contact.id if contact else None,
                    'owner_name': contact.Name if contact else None,
                    'owner_avatar_url': contact.Avatar_URL if contact else None,
                    'credentials': derive_credentials(contact) if contact else ''
                 })

            return jsonify(success=True, updated_sessions=updated_sessions)

        else:
            return jsonify(success=False, message="Invalid action or permissions."), 403

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during booking/assignment: {e}")
        return jsonify(success=False, message="An internal error occurred."), 500
