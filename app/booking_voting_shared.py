"""
Shared utilities for booking and voting pages.

This module contains common functions used by both booking_routes.py and voting_routes.py
to avoid code duplication while maintaining separation of concerns.
"""

from flask import session
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.orm import joinedload, subqueryload

from .models import SessionLog, SessionType, Contact, Meeting, Role, Waitlist, Vote
from . import db
from .auth.utils import is_authorized
from .utils import get_meetings_by_status, get_default_meeting_number


def assign_role_owner(target_log, new_owner_id):
    """
    Assigns an owner to a session log (and related logs if role is not distinct).
    Updates credentials and project codes.
    Syncs with Roster.
    
    Args:
        target_log: The SessionLog object to update (or one of them)
        new_owner_id: ID of the new owner (or None to unassign)
        
    Returns:
        list: List of updated SessionLog objects
    """
    from .models import SessionLog, SessionType, Role, Contact, Pathway, PathwayProject, Roster, Project
    from .utils import derive_credentials
    from .constants import SessionTypeID
    
    # 1. Identify all logs to update (handle is_distinct)
    session_type = target_log.session_type
    role_obj = session_type.role if session_type else None
    
    sessions_to_update = [target_log]
    
    if role_obj and not role_obj.is_distinct:
        # Find all logs for this role in this meeting
        target_role_id = role_obj.id
        current_owner_id = target_log.Owner_ID
        
        query = db.session.query(SessionLog)\
            .join(SessionType, SessionLog.Type_ID == SessionType.id)\
            .join(Role, SessionType.role_id == Role.id)\
            .filter(SessionLog.Meeting_Number == target_log.Meeting_Number)\
            .filter(Role.id == target_role_id)
        
        if current_owner_id is None:
            query = query.filter(SessionLog.Owner_ID.is_(None))
        else:
            query = query.filter(SessionLog.Owner_ID == current_owner_id)
            
        sessions_to_update = query.all()

    # 2. Prepare Data (Credentials, Project Code)
    owner_contact = Contact.query.get(new_owner_id) if new_owner_id else None
    new_credentials = derive_credentials(owner_contact)
    
    # Capture original owner from the target log (assuming others are consistent)
    original_owner_id = target_log.Owner_ID

    # 3. Update Logs
    for log in sessions_to_update:
        log.Owner_ID = new_owner_id
        log.credentials = new_credentials
        
        # Project Code Logic
        new_path_level = None
        if owner_contact:
            # Basic derivation
            new_path_level = log.derive_project_code(owner_contact)
            
            # Auto-Resolution from Next_Project for Prepared Speeches
            # This logic is copied from booking_routes.py
            if owner_contact.Next_Project and log.Type_ID == SessionTypeID.PREPARED_SPEECH:
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
                                log.Project_ID = pp.project_id
                                new_path_level = owner_contact.Next_Project
        
        log.project_code = new_path_level

    # 4. Sync Roster
    if role_obj:
        # Handle unassign old
        if original_owner_id and original_owner_id != new_owner_id:
            Roster.sync_role_assignment(target_log.Meeting_Number, original_owner_id, role_obj, 'unassign')
        
        # Handle assign new
        if new_owner_id:
            Roster.sync_role_assignment(target_log.Meeting_Number, new_owner_id, role_obj, 'assign')

    return sessions_to_update


def get_voter_identifier():
    """
    Helper to determine the voter identifier for the current user/guest.
    
    Returns:
        str: Voter identifier (user_id for authenticated users, token for guests)
    """
    if current_user.is_authenticated:
        return f"user_{current_user.id}"
    elif 'voter_token' in session:
        return session['voter_token']
    return None


def get_user_info():
    """
    Gets user information from current_user.
    
    Returns:
        tuple: (user object, contact_id)
    """
    if current_user.is_authenticated:
        user = current_user
        current_user_contact_id = user.Contact_ID
    else:
        user = None
        current_user_contact_id = None
    return user, current_user_contact_id


def get_meetings(limit_past=5, status_filter=None):
    """
    Fetches meetings based on optional status filter.
    
    Args:
        limit_past: Number of past meetings to include
        status_filter: Optional list of status values to filter by (e.g., ['running', 'finished'])
    
    Returns:
        tuple: (meetings list, default meeting number)
    """
    all_meetings_tuples = get_meetings_by_status(
        limit_past=limit_past, columns=[Meeting.Meeting_Number, Meeting.Meeting_Date])
    
    # Apply status filter if provided
    if status_filter:
        filtered_meetings = []
        for meeting_num, meeting_date in all_meetings_tuples:
            meeting = Meeting.query.filter_by(Meeting_Number=meeting_num).first()
            if meeting and meeting.status in status_filter:
                filtered_meetings.append((meeting_num, meeting_date))
        all_meetings_tuples = filtered_meetings
    
    default_meeting_num = get_default_meeting_number()
    
    return all_meetings_tuples, default_meeting_num


def fetch_session_logs(selected_meeting_number, meeting_obj=None):
    """
    Fetches session logs for a given meeting, filtering by user role.
    
    Args:
        selected_meeting_number: Meeting number to fetch logs for
        meeting_obj: Optional meeting object for authorization check
    
    Returns:
        list: Session logs with eager-loaded relationships
    """
    query = db.session.query(SessionLog)\
        .options(
            joinedload(SessionLog.session_type).joinedload(SessionType.role),
            joinedload(SessionLog.owner),
            subqueryload(SessionLog.waitlists).joinedload(Waitlist.contact)
        )\
        .join(SessionType, SessionLog.Type_ID == SessionType.id)\
        .join(Role, SessionType.role_id == Role.id)\
        .filter(SessionLog.Meeting_Number == selected_meeting_number)\
        .filter(Role.name != '', Role.name.isnot(None))

    if not is_authorized('BOOKING_ASSIGN_ALL', meeting=meeting_obj):
        query = query.filter(Role.type != 'officer')

    return query.all()


def consolidate_roles(session_logs):
    """
    Consolidates session logs into a dictionary of roles.
    Groups by (role_id, owner_id) unless role is marked as distinct.
    
    Args:
        session_logs: List of SessionLog objects
    
    Returns:
        dict: Consolidated roles dictionary
    """
    roles_dict = {}

    for log in session_logs:
        if not log.session_type or not log.session_type.role:
            continue

        role_obj = log.session_type.role
        role_name = role_obj.name.strip()
        role_id = role_obj.id
        owner_id = log.Owner_ID
        
        is_distinct = role_obj.is_distinct

        if is_distinct:
            dict_key = f"{role_id}_{owner_id}_{log.id}"
        else:
            dict_key = f"{role_id}_{owner_id}"

        if dict_key not in roles_dict:
            roles_dict[dict_key] = {
                'role': role_name,
                'role_key': role_name,
                'role_obj': role_obj,
                'owner_id': owner_id,
                'owner_name': log.owner.Name if log.owner else None,
                'owner_avatar_url': log.owner.Avatar_URL if log.owner else None,
                'session_ids': [],
                'type_id': log.Type_ID,
                'speaker_name': log.Session_Title.strip() if role_name == "Individual Evaluator" and log.Session_Title else None,
                'waitlist': [],
                'logs': []
            }

        roles_dict[dict_key]['session_ids'].append(log.id)
        roles_dict[dict_key]['logs'].append(log)

    # Consolidate waitlists for each group
    for dict_key, role_data in roles_dict.items():
        seen_waitlist_ids = set()
        for log in role_data['logs']:
            for waitlist_entry in log.waitlists:
                if waitlist_entry.contact_id not in seen_waitlist_ids:
                    role_data['waitlist'].append({
                        'name': waitlist_entry.contact.Name,
                        'id': waitlist_entry.contact_id,
                        'avatar_url': waitlist_entry.contact.Avatar_URL
                    })
                    seen_waitlist_ids.add(waitlist_entry.contact_id)
        del role_data['logs']

    return roles_dict


def group_roles_by_category(roles):
    """
    Groups roles by award_category and sorts groups by priority.
    
    Args:
        roles: List of role dictionaries
    
    Returns:
        list: List of tuples [(category_name, [list_of_roles]), ...]
    """
    from itertools import groupby
    
    grouped = []
    for key, group in groupby(roles, key=lambda x: x.get('award_category')):
        grouped.append((key, list(group)))

    return grouped


def get_best_award_ids(selected_meeting):
    """
    Gets the set of best award IDs for a meeting.
    
    Args:
        selected_meeting: Meeting object
    
    Returns:
        set: Set of award IDs
    """
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
