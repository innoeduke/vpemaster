# vpemaster/utils.py

from flask import current_app
# Ensure Project model is imported if needed elsewhere
from .models import Project, Meeting, SessionLog, Pathway, PathwayProject, Achievement, Contact, Club, SessionType, MeetingRole, OwnerMeetingRoles
from .auth.permissions import Permissions
from .club_context import get_current_club_id
from . import db
import re

import os
import hashlib
from sqlalchemy import distinct
from sqlalchemy.orm import joinedload
import re

# Compile regex pattern once for performance
LEVEL_CODE_PATTERN = re.compile(r"([A-Z]+)(\d+)")


def extract_level_from_path_code(path_level_str):
    """
    Parse pathway abbreviation and level from code string.
    
    Args:
        path_level_str (str): Code string like "SR5", "EH2", "PM1.1"
    
    Returns:
        tuple: (pathway_abbr, level) or (None, None) if parsing fails
               Example: "SR5" → ("SR", 5), "EH2.3" → ("EH", 2)
    """
    if not path_level_str:
        return None, None
    
    match = LEVEL_CODE_PATTERN.match(path_level_str)
    if match:
        pathway_abbr = match.group(1)
        level = int(match.group(2))
        return pathway_abbr, level
    
    return None, None


def build_pathway_project_cache(project_ids=None, pathway_ids=None):
    """
    Pre-fetch PathwayProject data for efficient O(1) lookups.
    Reduces N database queries in loops to 1-2 queries total.
    
    Args:
        project_ids (list, optional): List of project IDs to fetch data for
        pathway_ids (list, optional): List of pathway IDs to fetch data for
    
    Returns:
        dict: {project_id: {pathway_id: PathwayProject}}
              Allows O(1) lookup: cache[project_id][pathway_id]
    """
    query = PathwayProject.query.options(joinedload(PathwayProject.pathway))
    
    # Apply filters if provided
    if project_ids:
        query = query.filter(PathwayProject.project_id.in_(project_ids))
    if pathway_ids:
        query = query.filter(PathwayProject.path_id.in_(pathway_ids))
    
    all_pp = query.all()
    
    # Build nested dictionary for fast lookups
    cache = {}
    for pp in all_pp:
        if pp.project_id not in cache:
            cache[pp.project_id] = {}
        cache[pp.project_id][pp.path_id] = pp
    
    return cache


def normalize_role_name(name):
    """
    Normalize role name for comparison.
    Strips whitespace, removes hyphens and spaces, converts to lowercase.
    
    Args:
        name (str): Role name to normalize
    
    Returns:
        str: Normalized name (e.g., "Topic Master" → "topicmaster")
    """
    if not name:
        return ""
    return name.strip().replace(' ', '').replace('-', '').lower()


def get_role_aliases():
    """
    Return mapping of role name aliases for flexible matching.
    
    Returns:
        dict: Alias mappings (both directions)
              Example: {'tme': 'toastmaster', 'toastmaster': 'tme', ...}
    """
    return {
        'topicmaster': 'topicsmaster',
        'topicsmaster': 'topicmaster',
        'tme': 'toastmaster',
        'toastmaster': 'tme',
        'ge': 'generalevaluator',
        'generalevaluator': 'ge',
        'evaluator': 'individualevaluator',
        'sergeantatarms': 'saa',
        'saa': 'sergeantatarms'
    }


def get_dropdown_metadata():
    """
    Fetch all dropdown metadata (pathways, roles, projects) in one
    place for consistency across views.
    
    Returns:
        dict: {
            'pathways': {type: [pathway_names]},
            'pathway_mapping': {name: abbr},
            'abbr_to_name': {abbr: name},
            'roles': {type: [role_names]},
            'projects': [project_dicts],
            'meeting_numbers': [numbers]
        }
    """
    from .models import MeetingRole, SessionLog, Ticket, AuthRole
    
    # Pathways
    all_pathways = Pathway.query.filter(Pathway.type != 'dummy').order_by(Pathway.name).all()
    pathway_mapping = {p.name: p.abbr for p in all_pathways}
    abbr_to_name = {p.abbr: p.name for p in all_pathways if p.abbr}
    
    grouped_pathways = {}
    for p in all_pathways:
        ptype = p.type or "Other"
        if ptype not in grouped_pathways:
            grouped_pathways[ptype] = []
        grouped_pathways[ptype].append(p.name)
    
    # Roles
    # Use get_current_club_id() to ensure we get the correct context-aware roles
    current_club_id = get_current_club_id()
    available_roles = MeetingRole.get_all_for_club(current_club_id)
    
    # Filter for standard/club-specific if needed, though get_all_for_club returns objects
    available_roles = [r for r in available_roles if r.type in ['standard', 'club-specific']]
    
    grouped_roles = {}
    for r in available_roles:
        rtype = r.type.replace('-', ' ').title()
        if rtype not in grouped_roles:
            grouped_roles[rtype] = []
        grouped_roles[rtype].append(r.name)
    
    # Projects
    projects = Project.query.order_by(Project.Project_Name).all()
    all_pp = db.session.query(PathwayProject, Pathway.abbr).join(Pathway).all()
    
    project_codes_lookup = {}
    for pp, path_abbr in all_pp:
        if pp.project_id not in project_codes_lookup:
            project_codes_lookup[pp.project_id] = {}
        project_codes_lookup[pp.project_id][path_abbr] = {
            'code': pp.code,
            'level': pp.level
        }
    
    projects_data = [
        {
            "id": p.id,
            "Project_Name": p.Project_Name,
            "path_codes": project_codes_lookup.get(p.id, {}),
            "Duration_Min": p.Duration_Min,
            "Duration_Max": p.Duration_Max
        }
        for p in projects
    ]
    
    # Meeting numbers
    # Join with Project to ensure we only get meetings with valid projects? 
    # Or just all meetings that have any session logs?
    meeting_numbers = sorted(
        [m[0] for m in db.session.query(distinct(SessionLog.Meeting_Number)).all()],
        reverse=True
    )
    
    # Speakers (contacts with roles)
    from .models import OwnerMeetingRoles
    speakers = db.session.query(Contact).join(OwnerMeetingRoles)\
        .distinct().order_by(Contact.Name).all()
    
    # All contacts (for impersonation dropdown)
    all_contacts = Contact.query.order_by(Contact.Name).all()

    # Tickets
    tickets = Ticket.query.order_by(Ticket.id).all()

    # Auth Roles
    auth_roles_list = AuthRole.query.order_by(AuthRole.name).all()
    
    return {
        'pathways': grouped_pathways,
        'pathway_mapping': pathway_mapping,
        'abbr_to_name': abbr_to_name,
        'roles': grouped_roles,
        'projects': projects_data,
        'meeting_numbers': meeting_numbers,
        'speakers': speakers,
        'all_contacts': all_contacts,
        'tickets': tickets,
        'auth_roles': auth_roles_list
    }


def get_project_code(project_id, context_path_name=None):
    """
    Returns the project code based on project_id, preferring a specific pathway context.

    Args:
        project_id (int): The ID of the project
        context_path_name (str): Optional. The name of the pathway to prefer (e.g. user's current path).

    Returns:
        str: The project code (e.g., "PM1.1", "DL2", "TM1.0") or "" if not found.
    """
    if not project_id:
        return ""

    # Fetch project
    project = db.session.get(Project, project_id)
    if not project:
        return ""

    return project.get_code(context_path_name)


def update_next_project(contact):
    """
    Recalculates the Next_Project for a contact based on their Current_Path,
    their current Credentials (which reflect highest Level achievements),
    and completed speech logs.
    """
    if not contact or not contact.Current_Path:
        if contact:
            contact.Next_Project = None
        return

    if contact.Current_Path == "Distinguished Toastmasters":
        contact.Next_Project = None
        return

    pathway = Pathway.query.filter_by(name=contact.Current_Path).first()
    if not pathway or not pathway.abbr:
        return

    code_suffix = pathway.abbr
    
    # 1. Determine start_level based on credentials
    # Credentials are expected to be in format "AbbrN" e.g. "PM2"
    start_level = 1
    if contact.credentials:
        match = re.match(rf"^{code_suffix}(\d+)$", contact.credentials.strip().upper())
        if match:
            level_achieved = int(match.group(1))
            if level_achieved >= 5:
                contact.Next_Project = None
                return
            start_level = level_achieved + 1
    
    # 2. Find the first incomplete project from start_level onwards
    # Get all completed project IDs for this contact
    completed_project_ids = {
        log.Project_ID for log in SessionLog.query.join(SessionType).join(MeetingRole, SessionType.role_id == MeetingRole.id).join(Meeting, SessionLog.Meeting_Number == Meeting.Meeting_Number).filter(
            db.exists().where(
                db.and_(
                    OwnerMeetingRoles.contact_id == contact.id,
                    OwnerMeetingRoles.meeting_id == Meeting.id,
                    OwnerMeetingRoles.role_id == MeetingRole.id,
                    db.or_(
                        OwnerMeetingRoles.session_log_id == SessionLog.id,
                        OwnerMeetingRoles.session_log_id.is_(None)
                    )
                )
            )
        ).filter(SessionLog.Status=='Completed').all() if log.Project_ID
    }

    for level in range(start_level, 6):
        # Query PathwayProject for this path and level, ordered by code.
        path_projects = PathwayProject.query.filter(
            PathwayProject.path_id == pathway.id,
            PathwayProject.code.like(f"{level}.%")
        ).order_by(PathwayProject.code.asc()).all()

        for pp in path_projects:
            if pp.project_id not in completed_project_ids:
                contact.Next_Project = f"{code_suffix}{pp.code}"
                return

    # If all projects in all levels are done
    contact.Next_Project = None


def recalculate_contact_metadata(contact):
    """
    Update Contact metadata (DTM, Completed_Paths, credentials, Next_Project) 
    strictly based on the Achievements table and SessionLogs for this contact 
    AND all related contact records (same email or same user).
    Does NOT commit to DB.
    """
    if not contact:
        return

    # Find all related contact IDs (same email or same linked user)
    related_contact_ids = {contact.id}
    
    # 1. By Email
    if contact.Email:
        email_contacts = db.session.query(Contact.id).filter(
            Contact.Email == contact.Email
        ).all()
        for (c_id,) in email_contacts:
            related_contact_ids.add(c_id)
            
    # 2. By Linked User (across all clubs)
    user_ids = {uc.user_id for uc in contact.user_club_records if uc.user_id}
    if user_ids:
        from .models import UserClub
        user_contacts = db.session.query(UserClub.contact_id).filter(
            UserClub.user_id.in_(user_ids)
        ).all()
        for (c_id,) in user_contacts:
            if c_id:
                related_contact_ids.add(c_id)

    # Fetch achievements for ALL related contacts
    achievements = Achievement.query.filter(
        Achievement.contact_id.in_(list(related_contact_ids))
    ).all()
    
    # 1. DTM
    is_dtm = False
    for a in achievements:
        if a.achievement_type == 'program-completion' and a.path_name == 'Distinguished Toastmasters':
            is_dtm = True
            break
    
    # Preserve existing DTM=True if not found above
    if contact.DTM:
        contact.DTM = True
    else:
        contact.DTM = is_dtm

    # 2. Completed_Paths
    completed_set = set()
    
    # Collect existing paths from all related contacts to ensure no data loss
    related_contacts = Contact.query.filter(Contact.id.in_(list(related_contact_ids))).all()
    for c in related_contacts:
        if c.Completed_Paths:
            parts = [p.strip() for p in str(c.Completed_Paths).split('/') if p.strip()]
            completed_set.update(parts)

    # Add paths found in achievements for any related contact
    for a in achievements:
        if a.achievement_type == 'path-completion':
            pathway = Pathway.query.filter_by(name=a.path_name).first()
            if pathway and pathway.abbr:
                completed_set.add(f"{pathway.abbr}5")
    
    if completed_set:
        contact.Completed_Paths = "/".join(sorted(list(completed_set)))
    else:
        # Only set to None if it was already None/empty and no new paths found
        contact.Completed_Paths = None

    # 3. Credentials
    new_credentials = None
    if contact.Current_Path:
        # We only check achievements for the Current_Path in THIS contact's context
        # (Though we could arguably check globally too)
        level_achievements = [
            a for a in achievements 
            if a.achievement_type == 'level-completion' and a.path_name == contact.Current_Path and a.level
        ]
        if level_achievements:
            max_level = max(a.level for a in level_achievements)
            pathway = Pathway.query.filter_by(name=contact.Current_Path).first()
            if pathway and pathway.abbr:
                new_credentials = f"{pathway.abbr}{max_level}"
        else:
            path_comp = next((a for a in achievements if a.achievement_type == 'path-completion' and a.path_name == contact.Current_Path), None)
            if path_comp:
                pathway = Pathway.query.filter_by(name=contact.Current_Path).first()
                if pathway and pathway.abbr:
                    new_credentials = f"{pathway.abbr}5"
    
    if contact.DTM:
        contact.credentials = 'DTM'
    elif new_credentials:
        contact.credentials = new_credentials

    # 4. Next Project
    update_next_project(contact)


def sync_contact_metadata(contact_id):
    """
    Update Contact metadata for a specific contact and all related contacts 
    (same person in different clubs) and commit to DB.
    """
    primary_contact = db.session.get(Contact, contact_id)
    if not primary_contact:
        return None

    # Find all related contact IDs
    related_contact_ids = {primary_contact.id}
    if primary_contact.Email:
        email_contacts = db.session.query(Contact.id).filter(
            Contact.Email == primary_contact.Email
        ).all()
        for (c_id,) in email_contacts:
            related_contact_ids.add(c_id)
            
    user_ids = {uc.user_id for uc in primary_contact.user_club_records if uc.user_id}
    if user_ids:
        from .models import UserClub
        user_contacts = db.session.query(UserClub.contact_id).filter(
            UserClub.user_id.in_(user_ids)
        ).all()
        for (c_id,) in user_contacts:
            if c_id:
                related_contact_ids.add(c_id)

    # Update all related contacts
    contacts_to_update = Contact.query.filter(Contact.id.in_(list(related_contact_ids))).all()
    for contact in contacts_to_update:
        recalculate_contact_metadata(contact)
        db.session.add(contact)
    
    db.session.commit()
    return primary_contact



def derive_credentials(contact):
    """
    Derives the credentials string for a given contact.
    - Returns 'DTM' for DTMs.
    - Returns 'Guest' for Guests.
    - Returns the synced credentials field for Members/Officers.
    """
    if not contact:
        return ''

    if contact.DTM:
        return 'DTM'
    elif contact.Type == 'Guest':
        return "Guest"
    else:
        return contact.credentials or ''


def is_valid_for_vote(request, meeting_number, voter_identifier):
    """
    Validates if a user can vote for a specific meeting.

    This function ensures that:
    1. Each user can only vote once per meeting
    2. Users can vote for different meetings
    3. Voting is tracked anonymously without storing personal information

    Args:
        request (Request): Flask request object
        meeting_number (int): The meeting number to vote for
        voter_identifier (str): A unique identifier for the voter (e.g. hashed IP + User Agent)

    Returns:
        tuple: (is_valid, message) where is_valid is a boolean and message explains the result
    """
    from flask import session
    import hashlib

    # Create a unique key for this meeting and voter combination
    vote_key = f"vote_{meeting_number}_{voter_identifier}"

    # Check if this voter has already voted for this meeting
    if session.get(vote_key):
        return False, "You have already voted for this meeting."

    # Mark that this user has voted for this meeting
    session[vote_key] = True

    return True, "Vote recorded successfully."


def get_unique_identifier(request):
    """
    Generates a unique identifier for a voter based on their IP address and user agent.

    This function creates a SHA-256 hash of the user's IP address and user agent string,
    which can be used to identify unique voters without storing personal information.

    Args:
        request (Request): Flask request object

    Returns:
        str: A SHA-256 hash representing the unique voter identifier
    """
    # Get the user's IP address
    if request.headers.get('X-Forwarded-For'):
        ip_address = request.headers.get(
            'X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        ip_address = request.headers.get('X-Real-IP')
    else:
        ip_address = request.remote_addr

    # Get the user agent string
    user_agent = request.headers.get('User-Agent', '')

    # Combine IP and user agent
    combined_string = f"{ip_address}{user_agent}"

    # Generate and return SHA-256 hash
    return hashlib.sha256(combined_string.encode('utf-8')).hexdigest()





def get_meetings_by_status(limit_past=8, columns=None, status_filter=None):
    """
    Fetches meetings, categorizing them as 'active' or 'past' based on status.
    
    Args:
        limit_past (int): The maximum number of past meetings to retrieve.
        columns (list): A list of specific Meeting columns to query. 
                        If None, queries the full Meeting object.
        status_filter (list): Optional list of status strings to filter by.
                              If provided, overrides the default active/past logic
                              for simpler queries.

    Returns:
        tuple: (all_meetings, default_meeting_num)
               - all_meetings: A sorted list of meeting objects or tuples.
               - default_meeting_num: The number of the soonest 'not started' meeting.
    """
    from flask_login import current_user
    is_guest = not current_user.is_authenticated or \
               (hasattr(current_user, 'primary_role_name') and current_user.primary_role_name == 'Guest')

    query_cols = [Meeting] if columns is None else columns
    
    # --- Mode 1: Simple Filter (if status_filter provided) ---
    if status_filter:
        # Restriction for Guest: cannot view finished meetings
        effective_status_filter = status_filter
        if is_guest and 'finished' in status_filter:
            effective_status_filter = [s for s in status_filter if s != 'finished']

        query = db.session.query(*query_cols)\
            .filter(Meeting.status.in_(effective_status_filter))\
            .join(SessionLog, Meeting.Meeting_Number == SessionLog.Meeting_Number)\
            .distinct()\
            .order_by(Meeting.Meeting_Number.desc())
            
        all_meetings = query.all()
        default_meeting_num = get_default_meeting_number()
        return all_meetings, default_meeting_num

    # --- Mode 2: Default Hybrid Active/Past Logic ---
    club_id = get_current_club_id()

    # Fetch active meetings ('unpublished', 'not started', or 'running')
    # Updated: Always include 'unpublished' so list is same for all users
    active_statuses = ['not started', 'running', 'unpublished']
        
    active_query = db.session.query(*query_cols)\
        .filter(Meeting.status.in_(active_statuses))
    
    if club_id:
        active_query = active_query.filter(Meeting.club_id == club_id)
        
    active_meetings = active_query.order_by(Meeting.Meeting_Number.desc()).all()

    # Manager check removed as 'unpublished' is now always included

    active_meetings.sort(key=lambda m: m.Meeting_Number, reverse=True)

    # Fetch recent inactive meetings ('finished' or 'cancelled')
    past_statuses = ['finished', 'cancelled']
    if is_guest:
        past_statuses = ['cancelled']
        
    past_query = db.session.query(*query_cols)\
        .filter(Meeting.status.in_(past_statuses))
    
    if club_id:
        past_query = past_query.filter(Meeting.club_id == club_id)
        
    past_query = past_query.order_by(Meeting.Meeting_Number.desc())
    if limit_past is not None:
        past_query = past_query.limit(limit_past)
    
    past_meetings = past_query.all()

    # Combine and sort all meetings by meeting number
    all_meetings = sorted(active_meetings + past_meetings,
                          key=lambda m: m.Meeting_Number, reverse=True)

    # Filter meetings to only those that have session logs
    # Note: For efficiency, we should do this in the origin query, but maintaining 
    # exact parity with original logic means filtering post-fetch or subquery.
    # The original logic used a subquery to filter only those in the result set.
    meetings_with_logs_subquery = db.session.query(
        distinct(SessionLog.Meeting_Number)).subquery()
    
    final_meetings = []
    
    # Optimize: Get all valid numbers in one go for the set check
    valid_numbers = {row[0] for row in db.session.query(meetings_with_logs_subquery).all()}
    
    for m in all_meetings:
        m_num = m.Meeting_Number if hasattr(m, 'Meeting_Number') else m[0] # Handle tuple vs obj
        if m_num in valid_numbers:
            final_meetings.append(m)

    default_meeting = get_default_meeting_number()

    return final_meetings, default_meeting


def get_default_meeting_number():
    """
    Determines the default meeting number based on priority:
    1. 'running' meeting
    2. Lowest numbered unfinished meeting ('not started' or 'unpublished')
    Returns None if neither is found.
    """
    # 1. Check for running meeting
    club_id = get_current_club_id()
    
    running_query = Meeting.query.filter_by(status='running')
    if club_id:
        running_query = running_query.filter(Meeting.club_id == club_id)
    
    running_meeting = running_query.first()
    if running_meeting:
        return running_meeting.Meeting_Number

    # 2. Check for next unfinished meeting (not started or unpublished)
    # Always include both statuses to ensure lower-numbered meetings are prioritized
    from .models import SessionLog
    upcoming_query = Meeting.query \
        .join(SessionLog, Meeting.Meeting_Number == SessionLog.Meeting_Number) \
        .filter(Meeting.status.in_(['not started', 'unpublished']))
    
    if club_id:
        upcoming_query = upcoming_query.filter(Meeting.club_id == club_id)
        
    upcoming_meeting = upcoming_query.order_by(Meeting.Meeting_Number.asc()) \
        .first()

    if upcoming_meeting:
        return upcoming_meeting.Meeting_Number
    
    return None

def get_session_voter_identifier():
    """
    Helper to determine the voter identifier for the current user/guest.
    Migrated from booking_voting_shared.py.
    
    Returns:
        str: Voter identifier (user_id for authenticated users, token for guests)
    """
    from flask import session
    from flask_login import current_user
    
    if current_user.is_authenticated:
        return f"user_{current_user.id}"
    elif 'voter_token' in session:
        return session['voter_token']
    return None


def get_current_user_info():
    """
    Gets user information from current_user.
    Migrated from booking_voting_shared.py (was get_user_info).
    
    Returns:
        tuple: (user object, contact_id)
    """
    from flask_login import current_user
    from .club_context import get_current_club_id
    if current_user.is_authenticated:
        user = current_user
        club_id = get_current_club_id()
        contact = user.get_contact(club_id)
        current_user_contact_id = contact.id if contact else None
    else:
        user = None
        current_user_contact_id = None
    return user, current_user_contact_id


def consolidate_session_logs(session_logs):
    """
    Consolidates session logs into a dictionary of roles.
    Groups by (role_id, owner_id) unless role is marked as distinct.
    Migrated from booking_voting_shared.py (was consolidate_roles).
    
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
        
        # Consolidation key for primary display (uses first owner)
        owner = log.owner
        owner_id = owner.id if owner else None
        
        has_single_owner = role_obj.has_single_owner

        if has_single_owner:
            dict_key = f"{role_id}_{owner_id}_{log.id}"
        else:
            dict_key = f"{role_id}_{owner_id}"

        if dict_key not in roles_dict:
            roles_dict[dict_key] = {
                'role': role_name,
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
    Migrated from booking_voting_shared.py.
    
    Args:
        roles: List of role dictionaries
    
    Returns:
        list: List of tuples [(category_name, [list_of_roles]), ...]
    """
    from itertools import groupby
    
    CATEGORY_PRIORITY = {
        'speaker': 1,
        'evaluator': 2,
        'role-taker': 3,
        'table-topic': 4,
        'none': 99
    }
    
    def get_priority(role):
        cat = role.get('award_category') or 'none'
        return CATEGORY_PRIORITY.get(cat, 99)

    grouped = []
    # Sort roles by priority first, then alphabetical for consistency within same priority (though distinct categories)
    roles.sort(key=lambda x: (get_priority(x), x.get('award_category') or ""))
    
    for key, group in groupby(roles, key=lambda x: x.get('award_category')):
        grouped.append((key, list(group)))

    return grouped




def process_avatar(file, contact_id):
    """
    Processes an uploaded image: crops to square, resizes to 300x300, 
    and saves as WebP. Returns the relative path to be stored in DB.
    """
    from PIL import Image
    from werkzeug.utils import secure_filename
    import os

    try:
        img = Image.open(file)
        
        # Preservation of transparency (RGBA)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        
        # Square crop
        width, height = img.size
        if width > height:
            left = (width - height) / 2
            top = 0
            right = (width + height) / 2
            bottom = height
        else:
            left = 0
            top = (height - width) / 2
            right = width
            bottom = (height + width) / 2
        
        img = img.crop((left, top, right, bottom))
        img = img.resize((300, 300), Image.Resampling.LANCZOS)
        
        # Save file as WebP
        filename = secure_filename(f"avatar_{contact_id}.webp")
        
        # Use configured root directory
        root_dir = current_app.config.get('AVATAR_ROOT_DIR', 'uploads/avatars')
        upload_folder = os.path.join(current_app.root_path, 'static', root_dir)
        
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        img.save(file_path, "WEBP", quality=80)
        
        # Return only filename as requested
        return filename
    except Exception as e:
        print(f"Error processing avatar for contact {contact_id}: {e}")
        return None


def process_club_logo(file, club_id):
    """
    Processes an uploaded club logo: crops/resizes to fit specific dimensions if needed, 
    but generally keeps aspect ratio or squares it. For consistency with avatars (and assuming 
    logos are often used in similar contexts like headers), we'll do a resize but maybe keep 
    original aspect ratio or fit within a box. 
    Let's go with a 'fit within 300x300' approach or similar to avatar but for clubs.
    Actually, logos can be rectangular. Let's just resize to max width/height of 500px 
    to save space, and convert to WebP.
    """
    from PIL import Image
    from werkzeug.utils import secure_filename
    import os

    try:
        img = Image.open(file)
        
        # Preservation of transparency (RGBA)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        
        # Resize if too large, maintaining aspect ratio
        img.thumbnail((500, 500), Image.Resampling.LANCZOS)
        
        # Save file as WebP
        filename = secure_filename(f"club_logo_{club_id}.webp")
        # Store in a separate folder or same? Let's use uploads/club_logos
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'club_logos')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        img.save(file_path, "WEBP", quality=85)
        
        return f"uploads/club_logos/{filename}"
    except Exception as e:
        print(f"Error processing logo for club {club_id}: {e}")
        return None

def get_terms():
    """
    Generate a list of half-year terms (e.g. '2025 Jan-Jun', '2025 Jul-Dec').
    Returns a list of dicts: {'label': str, 'start': str(YYYY-MM-DD), 'end': str(YYYY-MM-DD), 'id': str}
    Goes back 5 years and forward 1 year from today.
    """
    from datetime import datetime
    today = datetime.today()
    current_year = today.year
    terms = []
    
    # Generate terms from 5 years ago to next year
    for year in range(current_year - 5, current_year + 2):
        # Jan-Jun
        terms.append({
            'label': f"{year} Jan-Jun",
            'id': f"{year}_1",
            'start': f"{year}-01-01",
            'end': f"{year}-06-30"
        })
        # Jul-Dec
        terms.append({
            'label': f"{year} Jul-Dec",
            'id': f"{year}_2",
            'start': f"{year}-07-01",
            'end': f"{year}-12-31"
        })
    
    # Sort descending
    terms.sort(key=lambda x: x['start'], reverse=True)
    return terms


def get_active_term(terms):
    """
    Find the term corresponding to today's date.
    """
    from datetime import datetime
    today_str = datetime.today().strftime('%Y-%m-%d')
    for term in terms:
        if term['start'] <= today_str <= term['end']:
            return term
    return terms[0] if terms else None

def get_date_ranges_for_terms(term_ids, all_terms):
    """
    Get a list of (start_date, end_date) tuples for the specified term IDs.
    
    Args:
        term_ids (list): List of term IDs (e.g. ['2025_1', '2025_2'])
        all_terms (list): List of all available term dictionaries
        
    Returns:
        list: List of (start_date, end_date) tuples as date objects
    """
    from datetime import datetime
    ranges = []
    term_map = {t['id']: t for t in all_terms}
    
    for tid in term_ids:
        if tid in term_map:
            s_str = term_map[tid]['start']
            e_str = term_map[tid]['end']
            # Convert strings to date objects
            s_date = datetime.strptime(s_str, '%Y-%m-%d').date()
            e_date = datetime.strptime(e_str, '%Y-%m-%d').date()
            ranges.append((s_date, e_date))
            
    return ranges





