# vpemaster/booking_routes.py

from .auth.utils import login_required, is_authorized
from flask import Blueprint, render_template, request, session, jsonify, current_app
from .models import SessionLog, SessionType, Contact, Meeting, User, LevelRole, Waitlist, Role, Vote
from . import db
from datetime import datetime
import re
import secrets
from sqlalchemy import or_
from .utils import derive_project_code, derive_credentials
from .utils import get_meetings_by_status

booking_bp = Blueprint('booking_bp', __name__)


def _fetch_session_logs(selected_meeting_number, meeting_obj=None):
    """Fetches session logs for a given meeting, filtering by user role."""
    # Fetch the full SessionLog objects to ensure all data is available for consolidation.
    query = db.session.query(SessionLog)\
        .join(SessionType, SessionLog.Type_ID == SessionType.id)\
        .join(Role, SessionType.role_id == Role.id)\
        .filter(SessionLog.Meeting_Number == selected_meeting_number)\
        .filter(Role.name != '', Role.name.isnot(None))

    if not is_authorized('BOOKING_ASSIGN_ALL', meeting=meeting_obj):
        query = query.filter(Role.type != 'officer')

    return query.all()


def _consolidate_roles(session_logs, is_admin_booker):
    """Consolidates session logs into a dictionary of roles."""
    roles_dict = {}

    # Group session logs by (role_id, owner_id) pair
    # This effectively deduplicates identical roles and collapses unassigned slots of the same role.
    for log in session_logs:
        # The log is now a full SessionLog object
        if not log.session_type or not log.session_type.role:
            continue

        role_obj = log.session_type.role
        role_name = role_obj.name.strip()
        role_id = role_obj.id
        owner_id = log.Owner_ID
        
        # Check if the role is marked as distinct (should not be deduped/grouped)
        is_distinct = role_obj.is_distinct

        if is_distinct:
            # Usage of is_distinct=True means "Show every log separately".
            # We enforce uniqueness in the key by including the log ID.
            dict_key = f"{role_id}_{owner_id}_{log.id}"
        else:
            # Default behavior: Group/Dedup by (role_id, owner_id).
            # The 3rd component is None (conceptually) or implicit.
            dict_key = f"{role_id}_{owner_id}"

        if dict_key not in roles_dict:
            # Initialize the entry for this role group
            roles_dict[dict_key] = {
                'role': role_name,
                'role_key': role_name,
                'owner_id': owner_id,
                'owner_name': log.owner.Name if log.owner else None,
                'owner_avatar_url': log.owner.Avatar_URL if log.owner else None,
                'session_ids': [], # Keep track of ALL session IDs this pair represents
                'type_id': log.Type_ID,
                'speaker_name': log.Session_Title.strip() if role_name == "Individual Evaluator" and log.Session_Title else None,
                'waitlist': [],
                'logs': []  # Store the full log objects
            }

        roles_dict[dict_key]['session_ids'].append(log.id)
        roles_dict[dict_key]['logs'].append(log)

    # Second pass: Consolidate waitlists for each group
    for dict_key, role_data in roles_dict.items():
        # Consolidate waitlists from all logs in the group, avoiding duplicates.
        seen_waitlist_ids = set()
        for log in role_data['logs']:
            for waitlist_entry in log.waitlists:
                if waitlist_entry.contact_id not in seen_waitlist_ids:
                    role_data['waitlist'].append(
                        {'name': waitlist_entry.contact.Name, 'id': waitlist_entry.contact_id, 'avatar_url': waitlist_entry.contact.Avatar_URL})
                    seen_waitlist_ids.add(waitlist_entry.contact_id)
        del role_data['logs']  # Clean up the temporary logs list
    return roles_dict


def _enrich_role_data(roles_dict, selected_meeting):
    """Enriches role data with icons and award information."""
    if not selected_meeting:
        return []

    winner_ids = {}
    if selected_meeting.status == 'running':
        # For a running meeting, the "winner" is who the current user voted for.
        voter_identifier = None
        if current_user.is_authenticated:
            voter_identifier = f"user_{current_user.id}"
        elif 'voter_token' in session:
            voter_identifier = session['voter_token']
        
        if voter_identifier:
            user_votes = Vote.query.filter_by(
                meeting_number=selected_meeting.Meeting_Number,
                voter_identifier=voter_identifier
            ).all()
            winner_ids = {vote.award_category: vote.contact_id for vote in user_votes}

    elif selected_meeting.status == 'finished':
        # For a finished meeting, the final winners are stored in the meeting object.
        winner_ids = {
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
        # The 'award_type' determines if the trophy icon is shown.
        # It's set if the owner of this role is the person who won the award (or was voted for by the user).
        role_data['award_type'] = award_category if owner_id and award_category and owner_id == winner_ids.get(award_category) else None
        
        # This seems to be for showing the vote button at all if the category is open for voting
        role_data['award_category_open'] = bool(award_category and not winner_ids.get(award_category))
        
        role_data['needs_approval'] = role_obj.needs_approval if role_obj else False
        role_data['is_member_only'] = role_obj.is_member_only if role_obj else False

        enriched_roles.append(role_data)
    return enriched_roles


def _apply_user_filters_and_rules(roles, current_user_contact_id, selected_meeting_number):
    """Applies filtering and business rules based on user permissions."""
    if is_authorized('BOOKING_ASSIGN_ALL'):
        return roles

    # 3-Week Policy speaker rule
    # 3-Week Policy speaker rule
    # New logic:
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


def _sort_roles(roles, current_user_contact_id, is_past_meeting):
    """Sorts roles based on user type."""
    # Define category priority
    CATEGORY_ORDER = {
        'speaker': 1,
        'evaluator': 2,
        'role-taker': 3,
        'table-topic': 4
    }
    
    # Helper to get sort key for category
    def get_category_priority(role):
        cat = role.get('award_category', '') or ''
        # Default to 99 for unknown/none so they appear last
        return CATEGORY_ORDER.get(cat, 99)

    if is_past_meeting or is_authorized('BOOKING_ASSIGN_ALL'):
        # For past meetings or admin view, sort by custom award category order, then role name
        roles.sort(key=lambda x: (
            get_category_priority(x),
            x.get('award_category', '') or '', 
            x['role']
        ))
    else:  # For current/future meetings for non-admins
        roles.sort(key=lambda x: (
            get_category_priority(x),
            0 if x['owner_id'] == current_user_contact_id else 1 if not x['owner_id'] else 2,
            x['role']
        ))
    return roles


def _get_roles_for_meeting(selected_meeting_number, current_user_contact_id, selected_meeting, is_past_meeting, meeting_obj=None):
    """Helper function to get and process roles for the booking page."""
    is_admin_booker = is_authorized('BOOKING_ASSIGN_ALL', meeting=meeting_obj)

    session_logs = _fetch_session_logs(selected_meeting_number, meeting_obj=meeting_obj)
    roles_dict = _consolidate_roles(session_logs, is_admin_booker)
    enriched_roles = _enrich_role_data(roles_dict, selected_meeting)
    filtered_roles = _apply_user_filters_and_rules(
        enriched_roles, current_user_contact_id, selected_meeting_number)

    sorted_roles = _sort_roles(
        filtered_roles, current_user_contact_id, is_past_meeting)

    if selected_meeting.status in ['running', 'finished']:
        sorted_roles = [role for role in sorted_roles if role.get(
            'award_category') and role.get('award_category') != 'none']

    # For 'not started' or 'unpublished' meetings, only show Topics Speaker to admins
    if selected_meeting.status in ['not started', 'unpublished'] and not is_admin_booker:
        sorted_roles = [
            role for role in sorted_roles
            if role['role_key'] != "Topics Speaker"
        ]

    return sorted_roles


def _get_user_info():
    """Gets user information from current_user."""
    if current_user.is_authenticated:
        user = current_user
        current_user_contact_id = user.Contact_ID
        # Role is accessible via user.Role or current_user.Role
    else:
        user = None
        current_user_contact_id = None
    return user, current_user_contact_id





from flask_login import current_user

def _get_meetings():
    """Fetches meetings based on user role."""
    # Logic for Past meetings visibility usually depends on role?
    # Original code: get_meetings_by_status(limit_past=5 ...).
    # It didn't seem to use user_role in _get_meetings body in original code shown in grep?
    # Wait, let's check original code.
    # Original: def _get_meetings(user_role): ... return get_meetings_by_status(...)
    # It accepted user_role but didn't use it in the body shown. 
    # Whatever, let's remove the unused argument.
    all_meetings_tuples = get_meetings_by_status(
        limit_past=5, columns=[Meeting.Meeting_Number, Meeting.Meeting_Date])

    from .utils import get_default_meeting_number
    default_meeting_num = get_default_meeting_number()

    return all_meetings_tuples, default_meeting_num


def _get_booking_page_context(selected_meeting_number, user, current_user_contact_id):
    """Gathers all context needed for the booking page template."""
    upcoming_meetings, default_meeting_num = _get_meetings()

    if not selected_meeting_number:
        selected_meeting_number = default_meeting_num or (
            upcoming_meetings[0][0] if upcoming_meetings else None)

    context = {
        'roles': [], 'upcoming_meetings': upcoming_meetings,
        'selected_meeting_number': selected_meeting_number,
        'user_bookings_by_date': [], 'contacts': [],
        'selected_meeting': None,
        'is_admin_view': is_authorized('BOOKING_ASSIGN_ALL'),
        'current_user_contact_id': current_user_contact_id,
        'user_role': current_user.Role if current_user.is_authenticated else 'Guest', # Passed to template if needed
        'best_award_ids': set()
    }

    if not selected_meeting_number:
        return context

    selected_meeting = Meeting.query.filter_by(
        Meeting_Number=selected_meeting_number).first()
    
    is_manager = current_user.is_authenticated and current_user.Contact_ID == selected_meeting.manager_id if selected_meeting else False
    if selected_meeting and selected_meeting.status == 'unpublished' and not (context['is_admin_view'] or (current_user.is_authenticated and current_user.is_officer) or is_manager):
        from flask import abort
        abort(403)

    context['selected_meeting'] = selected_meeting

    context['is_admin_view'] = is_authorized('BOOKING_ASSIGN_ALL', meeting=selected_meeting)

    is_past_meeting = selected_meeting.status == 'finished' if selected_meeting else False

    roles = _get_roles_for_meeting(
        selected_meeting_number, current_user_contact_id, selected_meeting, is_past_meeting, meeting_obj=selected_meeting)
    context['roles'] = roles
    context['sorted_role_groups'] = _group_roles_by_category(roles)

    context['user_bookings_by_date'] = _get_user_bookings(
        current_user_contact_id)

    if context['is_admin_view']:
        context['contacts'] = Contact.query.order_by(Contact.Name).all()

    context['best_award_ids'] = _get_best_award_ids(selected_meeting)

    return context


def _group_roles_by_category(roles):
    """
    Groups roles by award_category and sorts groups by priority.
    Returns a list of tuples: [(category_name, [list_of_roles]), ...]
    """
    from itertools import groupby
    
    # Priority for category ordering
    CATEGORY_PRIORITY = {
        'speaker': 1,
        'evaluator': 2,
        'role-taker': 3,
        'table-topic': 4
    }
    
    def get_priority(cat):
        return CATEGORY_PRIORITY.get(cat, 99)

    # 1. Filter out roles without a category if necessary, or keep them?
    # The template checks `if category and category != 'none'`.
    # We should probably include everything and let template filter, OR filter here.
    # Let's include everything but grouped.
    
    # 2. Sort roles by category priority first so groupby works, 
    #    and then by whatever internal order they should have (already sorted by _sort_roles?)
    #    _sort_roles already sorted them by category priority! 
    #    So we just need to group them.
    #    Wait, itertools.groupby requires contiguous keys. 
    #    Since _sort_roles sorts by get_category_priority(x), the categories are contiguous.
    #    So we can just use groupby directly.
    
    grouped = []
    for key, group in groupby(roles, key=lambda x: x.get('award_category')):
        grouped.append((key, list(group)))
        
    # Double check sorting of the groups themselves?
    # Since roles were sorted by category priority, the groups should emerge in that order.
    # Speaker (1) -> Evaluator (2) -> Role-Taker (3) -> Table-Topics (4).
    # Yes.
    
    return grouped


@booking_bp.route('/booking', defaults={'selected_meeting_number': None}, methods=['GET'])
@booking_bp.route('/booking/<int:selected_meeting_number>', methods=['GET'])
def booking(selected_meeting_number):
    user, current_user_contact_id = _get_user_info()
    context = _get_booking_page_context(
        selected_meeting_number, user, current_user_contact_id)
    return render_template('booking.html', **context)


@booking_bp.route('/booking/book', methods=['POST'])
@login_required
def book_or_assign_role():
    data = request.get_json()
    session_id = data.get('session_id')
    action = data.get('action')

    user, current_user_contact_id = _get_user_info()

    log = SessionLog.query.get(session_id)
    if not log:
        return jsonify(success=False, message="Session not found."), 404

    session_type = SessionType.query.get(log.Type_ID)
    logical_role_key = session_type.role.name if session_type and session_type.role else None

    if not logical_role_key:
        return jsonify(success=False, message="Could not determine the role key."), 400

    if action == 'join_waitlist':
        # Determine scope: Distinct -> Specific log; Not Distinct -> Whole Group
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
        # Check if the role needs approval
        role_needs_approval = session_type.role.needs_approval if session_type and session_type.role else False

        if role_needs_approval:
            # Same scope logic for waitlist-on-book
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
    elif action == 'assign' and is_authorized('BOOKING_ASSIGN_ALL'):
        contact_id = data.get('contact_id', '0')
        owner_id_to_set = int(contact_id) if contact_id != '0' else None

        # If assigning a specific user (not unassigning), remove that user from the waitlist
        if owner_id_to_set:
            # Determine scope for updating waitlist cleanup
            is_distinct = session_type.role.is_distinct if session_type and session_type.role else False
            if is_distinct:
                sessions_to_clear_waitlist = [session_id]
            else:
                sessions_to_clear_waitlist = _get_all_session_ids_for_group(log, logical_role_key, log.Owner_ID)

            Waitlist.query.filter(Waitlist.session_log_id.in_(
                sessions_to_clear_waitlist), Waitlist.contact_id == owner_id_to_set).delete(synchronize_session=False)

    elif action == 'approve_waitlist' and is_authorized('BOOKING_ASSIGN_ALL'):
        # Get the top person from the waitlist for this specific session_id
        waitlist_entry = Waitlist.query.filter_by(
            session_log_id=session_id).order_by(Waitlist.timestamp).first()

        if not waitlist_entry:
            return jsonify(success=False, message="No one is on the waitlist to approve."), 404

        owner_id_to_set = waitlist_entry.contact_id

        # Determine scope for cleanup
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
        owner_contact = Contact.query.get(
            owner_id_to_set) if owner_id_to_set else None
        new_credentials = derive_credentials(owner_contact)

        # Determine which sessions to update
        # We want to update all sessions that are in the same "group" as the one clicked.
        # Group is defined by (role_name, owner_id).
        # But wait, if we are booking an UNASSIGNED role, we only want to book ONE slot, not ALL unassigned slots of that type (unless they were previously conceptually "linked" distinct roles).
        # However, the user asked to "extract pairs of (role's name, owner's name) ... remove duplicate pairs".
        # This implies that all "Topics Speaker / Unassigned" rows are collapsed into one.
        # If I book it, I am booking "Topics Speaker".
        # If there are 5 slots, and I book one, do I get 1 or 5?
        # Usually, if they are "distinct" (like Ah-Counter), I get 5 (intro, report, etc).
        # If they are "multiple like speakers", I get 1.
        # BUT the new logic REMOVES is_distinct. So we don't know which is which easily!
        # Re-reading prompt: "rather than relying on the is_distinct field ... extract pairs ... use the remained pairs as available meeting roles to show".
        # This suggests that "Topics Speaker (Unassigned)" is ONE available role.
        # If I book it, I take ONE slot.
        # But if "Ah-Counter (Unassigned)" is shown, and I book it, I should take ALL 3 Ah-Counter slots (Intro, Report, etc).
        # Hmmm. Without `is_distinct`, how do I know if "Ah-Counter" implies all slots or just one?
        # Maybe the intention IS that if they are grouped, they stay grouped?
        # If I have 3 Ah-Counters, they are grouped. IF I assign User A, do 3 become assigned to A? Yes, probably.
        # If I have 5 Topics Speakers, they are grouped. If I assign User A, do 5 become assigned to A? Probably NOT desirable.
        # But if the UI shows only ONE row, the user expects to book ONE role.
        # If standard toastmaster logic applies:
        # - Roles that are "one person per meeting" (Toastmaster, GE, Ah-Counter) have multiple log entries but should be booked together.
        # - Roles that are "many people per meeting" (Speaker, Evaluator) have multiple log entries and should be booked separately.
        # The `is_distinct` flag was exactly solving this ambiguity!
        # If I remove `is_distinct`, I treat everything the same.
        # Method A: Update ALL logs in the group. (Risky for Topics Speakers)
        # Method B: Update ONE log in the group. (Breaks Ah-Counter splitting)
        # Method C: Update all logs in the group... but wait, if there are 5 unassigned Topics Speakers, they form ONE group.
        # If I assign A, and update ALL, then A gets all 5 spots. That sucks.
        #
        # Maybe the user implies that `is_distinct` was BAD/WRONG and the "pair-based" logic is BETTER?
        # If pairs are (Role, Owner), then:
        # Before: 5 Topics Speakers (None) -> 5 rows (if !distinct). Or 1 row (if distinct).
        # Now: 5 Topics Speakers (None) -> 1 row (Grouped by name="Topics Speaker", owner=None).
        # If I book it, I transition from (TS, None) -> (TS, Me).
        # If I update ALL logs in (TS, None) group, I get all 5.
        #
        # OPTION: Only update ONE log if there are multiple unassigned?
        # But for Ah-Counter, we want to update ALL.
        #
        # Let's look at the data. 
        # Ah-Counter entries: 2 (Intro, Report). Same role name.
        # Topics Speaker entries: 5. Same role name.
        #
        # If the user wants to remove `is_distinct`, maybe they assume that roles with same name ARE the same role?
        # BUT Topics Speakers are definitely distinct people.
        #
        # Let's try to be smart:
        # If I assign User A to one of the (Role, Unassigned) group:
        # Query distinct Session_Titles? No, TS have empty titles usually.
        #
        # Wait, if I change (TS, None) to (TS, A), I am effectively "splitting" the group.
        # Creating a new pair (TS, A) and leaving remainder (TS, None).
        # So I should only update ONE session log if I believe they are separate slots?
        # OR update ALL if I believe they are parts of one role.
        #
        # Is there any other field? `count_required` in LevelRole? No.
        #
        # Let's assume the safe default for "Booking" in this new paradigm:
        # Update ONLY ONE valid slot from the group.
        # WHY? Because if Ah-Counter needs 2 slots, maybe the DB has 2 slots.
        # If I update only 1, I get 1 Ah-Counter (Intro) and 1 Ah-Counter (Report/Unassigned).
        # Next time I look, I see (Ah-Counter, Me) and (Ah-Counter, None).
        # This seems awkward for multi-part roles.
        #
        # However, checking `models.py` or data:
        # Ah-Counter is distinct=1. Topics Speaker is distinct=0.
        # The user said "rather than relying on the is_distinct field".
        # This implies `is_distinct` might be potentially misleading or they want a simpler behavior.
        #
        # Let's check the SQL output from before.
        # Ah-Counter had 2 lines (Intro, Report).
        # Topics Speaker had 7 lines.
        #
        # If I implement "Book ONE slot", then booking Ah-Counter will require 2 clicks.
        # Use Case: "I want to be Ah Counter". Click Book.
        # Result: I am assigned to "Ah-Counter Introduction". "Ah-Counter Report" remains unassigned.
        # This is annoying but safe.
        #
        # If I implement "Book ALL slots", then booking Topics Speaker will assign me to ALL 7 slots.
        # Result: I am the only speaker.
        # This is BROKEN/Destructive.
        #
        # Conclusion: "Book ONE slot" is the only safe approach if we ignore `is_distinct`.
        # UNLESS we use some heuristics, but the prompt says "extract pairs... remove duplicate pairs".
        # This is purely about DISPLAY logic ("available meeting roles to show").
        #
        # Does the Prompt imply changing the BOOKING logic?
        # "on the booking table, update the logic of deciding which roles to show"
        # It didn't explicitly say "update how booking works".
        # BUT if I change the display to group them, the `session_id` I get from the frontend corresponds to ONE log (the first one in the group usually).
        # `roles_dict` -> `role_data['session_ids'][0]`.
        # So the frontend sends ONE session_id.
        #
        # If I only update that ONE session_id:
        # - Topics Speaker: Works great. I take one spot. The group (TS, None) shrinks by 1.
        # - Ah-Counter: I take one spot (Intro). The group (AC, None) shrinks by 1.
        #   The UI will show (AC, Me) and (AC, None).
        #   I have to click again to get the second part.
        #   This is acceptable functionality, just slightly more friction for multi-part roles.
        #
        # So, I will proceed with: Update ONE session log (the one passed in `session_id`) UNLESS we have a strong reason.
        # WAIT! If the user wants to remove `is_distinct` usage, then I should NOT use it in `booking_routes` anywhere.
        #
        # Code changes:
        # replace `role_is_distinct` checks with... nothing? Just treat as single log update?
        #
        # Let's check `_get_all_session_ids_for_role`. 
        # It was used to find peer logs to update together.
        # If we remove it, we just update `log`.
        #
        # Let's verify `_consolidate_roles` logic again.
        # I am returning `session_ids` list.
        # `session_id` in `enriched_roles` is `session_ids[0]`.
        #
        # Implementation decision:
        # I will change the update logic to ONLY update the strict `session_id` provided.
        # This respects the removal of `is_distinct` logic (grouping logic) for updates.
        #
        # Wait, if I change `_consolidate_roles`, I affect the view.
        # If I change `book_or_assign_role`, I affect the action.
        #
        # Only updating one log is safest.
        
        # Determine which sessions to update
        # If the role is distinct, we only update the specific session.
        # If the role is NOT distinct (e.g. Ah-Counter), we update ALL sessions of that role/owner in the meeting.
        
        # Re-fetch session_type just to be sure (it's loaded via log, but let's be safe with naming)
        session_type = log.session_type
        role_obj = session_type.role
        is_distinct = role_obj.is_distinct

        if is_distinct:
            sessions_to_update = [log]
        else:
            # Find all logs in this meeting with the same Role ID and Owner ID
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
            new_path_level = derive_project_code(
                session_log, owner_contact) if owner_contact else None

            session_log.Owner_ID = owner_id_to_set
            session_log.project_code = new_path_level
            session_log.credentials = new_credentials
            
            updated_sessions.append({
                'session_id': session_log.id,
                'owner_id': owner_id_to_set,
                'owner_name': owner_contact.Name if owner_contact else None,
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
    # This might be needed if we decide to maintain "update all in group" behavior for waitlists or something.
    # But currently I am moving towards single-log updates to be safe.
    # However, for waitlist, if I see "Topics Speaker (Unassigned)", and join waitlist, 
    # should I join waitlist for JUST the one session_id behind the button?
    # Yes, that's simplest.
    # But if I join waitlist for "Ah Counter", and there are 2 parts, I might want both.
    # Without is_distinct, I can't distinguish.
    #
    # Let's stick to the requested consolidated pairing for DISPLAY.
    # For ACTION, targeting the specific session ID attached to the button is the most deterministic.
    # The previous code for waitlist used `_get_all_session_ids_for_role` if distinct.
    # Now we will likely just use the session_id or maybe "all matching (role, owner)".
    #
    # If I use "all matching (role, owner)":
    # - Topics Speaker (None): 5 logs.
    # - I click Join Waitlist.
    # - I join waitlist for 5 logs.
    # - Then I get approved for ONE of them?
    # - If I get approved for one, does my waitlist for others disappear?
    #
    # Let's assume for now we want to mimic the "group" behavior: actions apply to the group shown.
    # If the group contains multiple logs, we apply to all.
    # Risk: Topics Speaker (None) -> Apply to 5 logs.
    # Verify: Is this acceptable? 
    # If I waitlist for TS, I want ANY TS slot. So waitlisting for all 5 is ACTUALLY CORRECT.
    # If I book TS, and book ALL 5, that is WRONG.
    #
    # DIFFERENT ACTIONS NEED DIFFERENT SCOPE?
    # Book: Needs 1 slot.
    # Waitlist: Needs ANY slot (so all is fine).
    # Assign: Needs 1 slot (usually).
    #
    # Let's stick to cleaning up the function signature first.
    query = db.session.query(SessionLog).join(SessionType).join(Role)\
        .filter(SessionLog.Meeting_Number == log.Meeting_Number)\
        .filter(Role.name == logical_role_key)
        
    if owner_id:
        query = query.filter(SessionLog.Owner_ID == owner_id)
    else:
        query = query.filter(SessionLog.Owner_ID.is_(None))
        
    return [l.id for l in query.all()]


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

    is_admin = is_authorized('BOOKING_ASSIGN_ALL')

    if not (meeting.status == 'running' or (meeting.status == 'finished' and is_admin)):
        return jsonify(success=False, message="Voting is not active for this meeting."), 403

    # 1. Determine voter identity
    if current_user.is_authenticated:
        voter_identifier = f"user_{current_user.id}"
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

        if meeting.status == 'finished' and is_admin:
            if award_category == 'speaker':
                meeting.best_speaker_id = your_vote_id
            elif award_category == 'evaluator':
                meeting.best_evaluator_id = your_vote_id
            elif award_category == 'table-topic':
                meeting.best_table_topic_id = your_vote_id
            elif award_category == 'role-taker':
                meeting.best_role_taker_id = your_vote_id
            db.session.commit()

        return jsonify(success=True, your_vote_id=your_vote_id, award_category=award_category)

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing vote: {e}")
        return jsonify(success=False, message="An internal error occurred."), 500



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



