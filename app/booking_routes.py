# vpemaster/booking_routes.py

from .auth.utils import login_required, is_authorized
from flask import Blueprint, render_template, request, session, jsonify, current_app
from .models import SessionLog, SessionType, Contact, Meeting, User, LevelRole
from . import db
from datetime import datetime
import re
from sqlalchemy import text, or_
from .utils import derive_current_path_level, ROLE_ICONS

booking_bp = Blueprint('booking_bp', __name__)


def _get_roles_for_meeting(selected_meeting_number, user_role, current_user_contact_id, selected_meeting):
    """Helper function to get and process roles for the booking page."""

    award_ids = {
        'Best_Speaker': selected_meeting.Best_Speaker_ID if selected_meeting else None,
        'Best_Evaluator': selected_meeting.Best_Evaluator_ID if selected_meeting else None,
        'Best_TT': selected_meeting.Best_TT_ID if selected_meeting else None,
        'Best_Roletaker': selected_meeting.Best_Roletaker_ID if selected_meeting else None,
    }

    query = db.session.query(
        SessionLog.id.label('session_id'),
        SessionType.Role.label('role'),
        SessionType.Role_Group.label('role_group'),
        SessionLog.Session_Title,
        SessionLog.Owner_ID,
        Contact.Name.label('owner_name')
    ).join(SessionType, SessionLog.Type_ID == SessionType.id)\
     .outerjoin(Contact, SessionLog.Owner_ID == Contact.id)\
     .filter(SessionLog.Meeting_Number == selected_meeting_number)\
     .filter(SessionType.Role != '', SessionType.Role.isnot(None))

    if not is_authorized(user_role, 'BOOKING_ASSIGN_ALL'):
        query = query.filter(SessionType.Role_Group != 'Officer')

    session_logs = query.all()

    roles_dict = {}
    for log in session_logs:
        role_key = log.role.strip() if log.role else ""
        speaker_name_for_display = None
        role_display = role_key

        # Roles that must always have unique entries (one row per session log):
        if role_key in ["Prepared Speaker", "Individual Evaluator", "Backup Speaker"]:

            if role_key == "Individual Evaluator" and (log.Session_Title or ''):
                speaker_name_for_display = log.Session_Title.strip()
                role_display = "Individual Evaluator"
            else:
                role_display = role_key
                speaker_name_for_display = None

            role_key_unique = f"{role_key}_{log.session_id}"

            roles_dict[role_key_unique] = {
                'role': role_display,
                'role_key': role_key,
                'owner_id': log.Owner_ID,
                'owner_name': log.owner_name,
                'session_ids': [log.session_id],
                'speaker_name': speaker_name_for_display,
            }

        # Roles that are unique per meeting and should be consolidated
        else:
            role_key_unique = role_key

            if role_key_unique not in roles_dict:
                roles_dict[role_key_unique] = {
                    'role': role_display,
                    'role_key': role_key,
                    'owner_id': log.Owner_ID,
                    'owner_name': log.owner_name,
                    'session_ids': [log.session_id],
                    'speaker_name': None,
                }
            else:
                roles_dict[role_key_unique]['session_ids'].append(
                    log.session_id)
                if log.Owner_ID:
                    roles_dict[role_key_unique]['owner_id'] = log.Owner_ID
                    roles_dict[role_key_unique]['owner_name'] = log.owner_name
                roles_dict[role_key_unique]['speaker_name'] = None

    roles_with_icons = []
    for key, role_data in roles_dict.items():
        role_data['icon'] = ROLE_ICONS.get(
            role_data['role_key'], ROLE_ICONS['Default'])
        role_data['session_id'] = role_data['session_ids'][0]

        role_key = role_data['role_key']
        owner_id = role_data['owner_id']
        award_type = None  # Default
        award_category_open = False
        award_category = None

        if owner_id and selected_meeting:
            if role_key in ['Prepared Speaker', 'Keynote Speaker', 'Presenter']:
                award_category = 'Best_Speaker'
            elif role_key == 'Individual Evaluator':
                award_category = 'Best_Evaluator'
            elif role_key == 'Topics Speaker':
                award_category = 'Best_TT'
            elif role_key in ['Toastmaster', 'General Evaluator', 'Topicmaster', 'Grammarian', 'Timer', 'Ah-Counter']:
                award_category = 'Best_Roletaker'

            if award_category:
                if owner_id == award_ids.get(award_category):  # Use .get() for safety
                    award_type = award_category

                # --- Step 3: Check if category is open (if category assigned and no winner) ---
                if not award_type and award_ids.get(award_category) is None:
                    award_category_open = True

        role_data['award_type'] = award_type
        role_data['award_category_open'] = award_category_open
        role_data['award_category'] = award_category

        roles_with_icons.append(role_data)

    # Apply filtering and sorting
    if not is_authorized(user_role, 'BOOKING_ASSIGN_ALL'):
        # Filter out roles booked by others
        roles_with_icons = [
            role for role in roles_with_icons
            if not role['owner_id'] or role['owner_id'] == current_user_contact_id
        ]

        # --- Backup Speaker Rule: Check if user already has one booked for the future ---
        has_upcoming_backup_speaker = False
        if current_user_contact_id:  # Only check if user is logged in and linked
            existing_backup_booking = db.session.query(SessionLog.id)\
                .join(Meeting, SessionLog.Meeting_Number == Meeting.Meeting_Number)\
                .join(SessionType, SessionLog.Type_ID == SessionType.id)\
                .filter(SessionLog.Owner_ID == current_user_contact_id)\
                .filter(SessionType.Role == "Backup Speaker")\
                .filter(Meeting.Meeting_Date >= datetime.today().date())\
                .first()
            if existing_backup_booking:
                has_upcoming_backup_speaker = True

        # If they have an upcoming backup speaker, remove available backup speaker slots
        if has_upcoming_backup_speaker:
            roles_with_icons = [
                role for role in roles_with_icons
                # Keep the role if it's NOT a Backup Speaker OR
                # if it IS a Backup Speaker AND the current user already owns it (allow seeing own booking)
                if role['role_key'] != 'Backup Speaker' or (role['role_key'] == 'Backup Speaker' and role['owner_id'] == current_user_contact_id)
            ]

        # 3-Week Policy speaker rule - Check config before applying
        pathway_mapping = current_app.config.get(
            'PATHWAY_MAPPING', {})  # Get pathway mapping
        user_contact = Contact.query.get(
            current_user_contact_id) if current_user_contact_id else None
        user_path = user_contact.Working_Path if user_contact else None
        code_suffix = pathway_mapping.get(user_path) if user_path else None

        if code_suffix:  # Only apply if user has a valid pathway
            three_meetings_ago = selected_meeting_number - 2
            recent_speaker_log = db.session.query(SessionLog.id).join(SessionType)\
                .filter(SessionLog.Owner_ID == current_user_contact_id)\
                .filter(SessionType.Role == 'Prepared Speaker')\
                .filter(SessionLog.Meeting_Number >= three_meetings_ago)\
                .filter(SessionLog.Meeting_Number <= selected_meeting_number).first()

            if recent_speaker_log:
                roles_with_icons = [
                    role for role in roles_with_icons
                    if role['role_key'] != 'Prepared Speaker' or (role['role_key'] == 'Prepared Speaker' and role['owner_id'] == current_user_contact_id)
                ]

        # Sort for members/officers: 1st your roles, 2nd available roles.
        roles_with_icons.sort(key=lambda x: (
            0 if x['owner_id'] == current_user_contact_id else 1 if not x['owner_id'] else 2,
            x['role']  # Sort alphabetically within groups
        ))

    else:
        # Sort for VPE/Admin by session_id (approximates meeting order)
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

    # Determine Default Level
    default_level = 1
    if user and user.contact and user.contact.Next_Project:
        next_project_str = user.contact.Next_Project
        match = re.match(r"([A-Z]+)(\d+)\.?(\d*)", next_project_str)
        if match:
            try:
                default_level = int(match.group(2))
            except (ValueError, IndexError):
                default_level = 1

    # Get selected level
    selected_level = request.args.get('level', default=default_level, type=int)

    today = datetime.today().date()
    
    soonest_upcoming_meeting = db.session.query(Meeting.Meeting_Number)\
        .filter(Meeting.Meeting_Date >= today)\
        .order_by(Meeting.Meeting_Number.asc())\
        .first()
    
    default_meeting_num = soonest_upcoming_meeting[0] if soonest_upcoming_meeting else None

    if is_authorized(user_role, 'BOOKING_ASSIGN_ALL'):
        # Admin view: All meetings, sorted DESC (newest first)
        future_meetings_query = db.session.query(Meeting.Meeting_Number, Meeting.Meeting_Date)\
            .filter(Meeting.Meeting_Date >= today)\
            .order_by(Meeting.Meeting_Number.desc()) # <-- CHANGED TO DESC

        past_meetings_query = db.session.query(Meeting.Meeting_Number, Meeting.Meeting_Date)\
            .filter(Meeting.Meeting_Date < today)\
            .order_by(Meeting.Meeting_Number.desc())\
            .limit(5)
        
        future_meetings_list = future_meetings_query.all()
        past_meetings_list = past_meetings_query.all()
        
        # Newest future meetings, then newest past meetings
        upcoming_meetings = future_meetings_list + past_meetings_list # <-- CHANGED ORDER
    else:
        # Member view: Only future meetings, sorted ASC (soonest first)
        upcoming_meetings = db.session.query(Meeting.Meeting_Number, Meeting.Meeting_Date)\
            .filter(Meeting.Meeting_Date >= today)\
            .order_by(Meeting.Meeting_Number.asc()).all() # <-- KEPT AS ASC

    if not selected_meeting_number:
        if default_meeting_num:
            selected_meeting_number = default_meeting_num
        elif upcoming_meetings:
            # Fallback to the first item in the list (for admins, this is newest past meeting)
            selected_meeting_number = upcoming_meetings[0][0]

    if not selected_meeting_number:
        return render_template('booking.html', roles=[], upcoming_meetings=[],
                               selected_meeting_number=None, user_bookings_by_date=[],
                               contacts=[], completed_roles=[], selected_level=selected_level, 
                               selected_meeting=None)

    selected_meeting = Meeting.query.filter_by(Meeting_Number=selected_meeting_number).first()
    best_award_ids = set()
    if selected_meeting:
        if selected_meeting.Best_TT_ID:
           best_award_ids.add(selected_meeting.Best_TT_ID)
        if selected_meeting.Best_Evaluator_ID:
           best_award_ids.add(selected_meeting.Best_Evaluator_ID)
        if selected_meeting.Best_Speaker_ID:
           best_award_ids.add(selected_meeting.Best_Speaker_ID)
        if selected_meeting.Best_Roletaker_ID:
           best_award_ids.add(selected_meeting.Best_Roletaker_ID)

    # Get roles for the selected meeting
    roles_with_icons = _get_roles_for_meeting(
        selected_meeting_number, user_role, current_user_contact_id, selected_meeting)

    # Get user's upcoming roles for the timeline
    user_bookings_query = db.session.query(
        SessionLog.id, SessionType.Role, Meeting.Meeting_Number, Meeting.Meeting_Date
    ).join(SessionType, SessionLog.Type_ID == SessionType.id)\
     .join(Meeting, SessionLog.Meeting_Number == Meeting.Meeting_Number)\
     .filter(SessionLog.Owner_ID == current_user_contact_id)\
     .filter(Meeting.Meeting_Date >= datetime.today().date())\
     .filter(SessionType.Role != '', SessionType.Role.isnot(None))\
     .order_by(Meeting.Meeting_Date, SessionType.Role).distinct()
    user_bookings = user_bookings_query.all()
    user_bookings_by_date = {}
    processed_roles = set()
    for log in user_bookings:
        role_meeting_key = (log.Meeting_Number, log.Role)
        if role_meeting_key in processed_roles:
            continue
        processed_roles.add(role_meeting_key)
        date_str = log.Meeting_Date.strftime('%Y-%m-%d')
        if date_str not in user_bookings_by_date:
            user_bookings_by_date[date_str] = {
                'date_info': {'meeting_number': log.Meeting_Number, 'short_date': log.Meeting_Date.strftime('%m/%d/%Y')},
                'bookings': []
            }
        user_bookings_by_date[date_str]['bookings'].append({
            'role': log.Role, 'role_key': log.Role, 'icon': ROLE_ICONS.get(log.Role, ROLE_ICONS['Default']), 'session_id': log.id
        })
    user_bookings_timeline = sorted(
        user_bookings_by_date.values(), key=lambda x: x['date_info']['meeting_number'])

    # --- Get Completed Roles using Raw SQL ---
    completed_roles = []
    if current_user_contact_id and selected_level:
        # Pattern to match the level in current_path_level
        level_pattern = f"%{selected_level}%"
        today = datetime.today().date()

        try:
            completed_logs_query = db.session.query(
                Meeting.Meeting_Number,
                SessionType.Role
            ).select_from(SessionLog)\
             .join(SessionType, SessionLog.Type_ID == SessionType.id)\
             .join(Meeting, SessionLog.Meeting_Number == Meeting.Meeting_Number)\
             .filter(SessionLog.Owner_ID == current_user_contact_id)\
             .filter(SessionType.Role.isnot(None))\
             .filter(SessionType.Role != '')\
             .filter(SessionType.Role != 'Prepared Speaker')\
             .filter(SessionLog.current_path_level.isnot(None))\
             .filter(SessionLog.current_path_level != '')\
             .filter(SessionLog.current_path_level.like(level_pattern))\
             .filter(Meeting.Meeting_Date < today)\
             .distinct()\
             .order_by(Meeting.Meeting_Number.desc(), SessionType.Role.asc())  # Order by meeting then role

            # Get the unique meeting/role pairs
            unique_completed_roles = completed_logs_query.all()

            # Now, for each unique pair, fetch ONE representative log entry
            # to get the date. This avoids multiple entries for the same role in the same meeting.
            processed_roles = set()  # Keep track of (meeting_num, role_name) already added
            for meeting_num, role_name in unique_completed_roles:
                role_meeting_key = (meeting_num, role_name)
                if role_meeting_key in processed_roles:
                    continue  # Skip if already processed

                # Find the date for this meeting (can fetch it once per meeting if needed,
                # but fetching with the role ensures we get a relevant entry)
                first_log_for_role = db.session.query(Meeting.Meeting_Date)\
                    .join(SessionLog, Meeting.Meeting_Number == SessionLog.Meeting_Number)\
                    .join(SessionType, SessionLog.Type_ID == SessionType.id)\
                    .filter(Meeting.Meeting_Number == meeting_num)\
                    .filter(SessionType.Role == role_name)\
                    .filter(SessionLog.Owner_ID == current_user_contact_id)\
                    .first()  # Get the first match to retrieve the date

                if first_log_for_role:
                    meeting_date = first_log_for_role.Meeting_Date
                    icon = ROLE_ICONS.get(role_name, ROLE_ICONS['Default'])
                    completed_roles.append({
                        'role': role_name,
                        'meeting_number': meeting_num,
                        'date': meeting_date.strftime('%Y-%m-%d'),
                        'icon': icon
                    })
                    processed_roles.add(role_meeting_key)  # Mark as processed

        except Exception as e:
            print(f"Error executing ORM query for completed roles: {e}")
            completed_roles = []  # Ensure it's empty on error

    # Get contacts for admin dropdown
    contacts = Contact.query.order_by(Contact.Name).all()

    return render_template('booking.html',
                           roles=roles_with_icons,
                           upcoming_meetings=upcoming_meetings,
                           selected_meeting_number=selected_meeting_number,
                           is_vpe_or_admin=(
                               user_role in ['Admin', 'VPE', 'Meeting Manager']),
                           current_user_contact_id=current_user_contact_id,
                           user_bookings_by_date=user_bookings_timeline,
                           contacts=contacts,
                           completed_roles=completed_roles,
                           selected_level=selected_level,
                           best_award_ids=best_award_ids)


@booking_bp.route('/booking/book', methods=['POST'])
@login_required
def book_or_assign_role():
    data = request.get_json()
    session_id = data.get('session_id')
    action = data.get('action')

    user = User.query.get(session.get('user_id'))
    current_user_contact_id = user.Contact_ID if user else None
    user_role = session.get('user_role')

    log = SessionLog.query.get(session_id)
    if not log:
        return jsonify(success=False, message="Session not found.")

    session_type_id = log.Type_ID
    session_type = SessionType.query.get(session_type_id)
    logical_role_key = session_type.Role if session_type else None

    if not logical_role_key:
        return jsonify(success=False, message="Could not determine the role key.")

    sessions_to_update_query = SessionLog.query.join(SessionType)\
        .filter(SessionLog.Meeting_Number == log.Meeting_Number)\
        .filter(SessionType.Role == logical_role_key)

    owner_id_to_set = None
    owner_contact = None

    if action == 'book':
        owner_id_to_set = current_user_contact_id
        if owner_id_to_set:
            owner_contact = Contact.query.get(owner_id_to_set)
    elif action == 'cancel':
        pass
    elif action == 'assign' and user_role in ['Admin', 'VPE', 'Meeting Manager']:
        contact_id = data.get('contact_id', '0')
        owner_id_to_set = int(contact_id) if contact_id != '0' else None
        if owner_id_to_set:
            owner_contact = Contact.query.get(owner_id_to_set)
    else:
        return jsonify(success=False, message="Invalid action or permissions.")

    new_path_level = derive_current_path_level(
        log, owner_contact) if owner_contact else None

    # --- Apply the update ---
    if logical_role_key in ["Prepared Speaker", "Individual Evaluator", "Backup Speaker"]:
        # Update only the specific log entry for these roles
        log_to_update = SessionLog.query.get(session_id)
        if log_to_update:
            log_to_update.Owner_ID = owner_id_to_set
            log_to_update.current_path_level = new_path_level  # Update path level
    else:
        # Update all log entries associated with this unique role in this meeting
        sessions_to_update = sessions_to_update_query.all()
        if not sessions_to_update:
            # This case should ideally not happen if the initial log was found
            return jsonify(success=False, message="No matching roles found to update.")

        # Apply the update to all found sessions for this role
        for session_log in sessions_to_update:
            session_log.Owner_ID = owner_id_to_set
            session_log.current_path_level = new_path_level

    # --- Commit and respond ---
    try:
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        # Consider logging the error e for debugging
        print(f"Error during booking/assignment: {e}")
        return jsonify(success=False, message="An internal error occurred. Please try again.")

@booking_bp.route('/booking/vote', methods=['POST'])
@login_required
def vote_for_award():
    if not is_authorized(session.get('user_role'), 'BOOKING_ASSIGN_ALL'):
        return jsonify(success=False, message="Permission denied."), 403

    data = request.get_json()
    meeting_number = data.get('meeting_number')
    contact_id = data.get('contact_id')
    award_category = data.get('award_category') # e.g., 'Best_Speaker'

    # --- START DEBUG LOGGING ---
    # This will print to your Flask console
    current_app.logger.debug("--- VOTE_FOR_AWARD DEBUG ---")
    current_app.logger.debug(f"Raw JSON data received: {data}")
    current_app.logger.debug(f"Extracted meeting_number: {meeting_number} (Type: {type(meeting_number)})")
    current_app.logger.debug(f"Extracted contact_id: {contact_id} (Type: {type(contact_id)})")
    current_app.logger.debug(f"Extracted award_category: {award_category} (Type: {type(award_category)})")
    # --- END DEBUG LOGGING ---

    if not all([meeting_number, contact_id, award_category]):
        current_app.logger.warning(f"Validation failed: 'if not all(...)' was True.")
        current_app.logger.warning(f"Boolean checks: meeting_number={bool(meeting_number)}, contact_id={bool(contact_id)}, award_category={bool(award_category)}")
        return jsonify(success=False, message="Missing data."), 400

    meeting = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
    if not meeting:
        return jsonify(success=False, message="Meeting not found."), 404

    new_winner_id = None
    
    try:
        if award_category == 'Best_Speaker':
            if meeting.Best_Speaker_ID == contact_id:
                meeting.Best_Speaker_ID = None
            else:
                meeting.Best_Speaker_ID = contact_id
            new_winner_id = meeting.Best_Speaker_ID
        
        elif award_category == 'Best_Evaluator':
            if meeting.Best_Evaluator_ID == contact_id:
                meeting.Best_Evaluator_ID = None
            else:
                meeting.Best_Evaluator_ID = contact_id
            new_winner_id = meeting.Best_Evaluator_ID
        
        elif award_category == 'Best_TT':
            if meeting.Best_TT_ID == contact_id:
                meeting.Best_TT_ID = None
            else:
                meeting.Best_TT_ID = contact_id
            new_winner_id = meeting.Best_TT_ID
        
        elif award_category == 'Best_Roletaker':
            if meeting.Best_Roletaker_ID == contact_id:
                meeting.Best_Roletaker_ID = None
            else:
                meeting.Best_Roletaker_ID = contact_id
            new_winner_id = meeting.Best_Roletaker_ID
        
        else:
            return jsonify(success=False, message="Invalid award category."), 400

        db.session.commit()
        return jsonify(success=True, new_winner_id=new_winner_id, award_category=award_category)

    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500