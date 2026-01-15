# vpemaster/utils.py

from flask import current_app
# Ensure Project model is imported if needed elsewhere
from .models import Project, Meeting, SessionLog, Pathway, PathwayProject, Achievement, Contact
from .auth.permissions import Permissions
from . import db
import re
import configparser
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
        'generalevaluator': 'ge'
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
    from .models import MeetingRole, SessionLog
    
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
    available_roles = MeetingRole.query.filter(
        MeetingRole.type.in_(['standard', 'club-specific'])
    ).order_by(MeetingRole.name).all()
    
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
    meeting_numbers = sorted(
        [m[0] for m in db.session.query(distinct(SessionLog.Meeting_Number)).join(Project).all()],
        reverse=True
    )
    
    # Speakers (contacts with logs)
    speakers = db.session.query(Contact).join(
        SessionLog, Contact.id == SessionLog.Owner_ID
    ).distinct().order_by(Contact.Name).all()
    
    # All contacts (for impersonation dropdown)
    all_contacts = Contact.query.order_by(Contact.Name).all()
    
    return {
        'pathways': grouped_pathways,
        'pathway_mapping': pathway_mapping,
        'abbr_to_name': abbr_to_name,
        'roles': grouped_roles,
        'projects': projects_data,
        'meeting_numbers': meeting_numbers,
        'speakers': speakers,
        'all_contacts': all_contacts
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
        log.Project_ID for log in SessionLog.query.filter_by(
            Owner_ID=contact.id, 
            Status='Completed'
        ).all() if log.Project_ID
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
    strictly based on the Achievements table and SessionLogs.
    Does NOT commit to DB.
    """
    if not contact:
        return

    achievements = Achievement.query.filter_by(contact_id=contact.id).all()
    
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
    
    # Start with existing paths to ensure we don't lose manual/historical entries
    if contact.Completed_Paths:
        existing_parts = [p.strip() for p in str(contact.Completed_Paths).split('/') if p.strip()]
        completed_set.update(existing_parts)

    # Add paths found in achievements
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
    # Else: If new_credentials is None, do not overwrite if existing credentials exist.
    # Logic: "if credentials is not blank and no achievement records ... keep the existing value"

    # 4. Next Project
    update_next_project(contact)


def sync_contact_metadata(contact_id):
    """
    Update Contact metadata and commit to DB.
    """
    contact = db.session.get(Contact, contact_id)
    if not contact:
        return None

    recalculate_contact_metadata(contact)

    db.session.add(contact)
    db.session.commit()
    return contact



def derive_credentials(contact):
    """
    Derives the credentials string for a given contact.
    - Returns 'DTM' for DTMs.
    - Formats for Guests (e.g., "Guest@Club").
    - Returns the synced credentials field for Members/Officers.
    """
    if not contact:
        return ''

    if contact.DTM:
        return 'DTM'
    elif contact.Type == 'Guest':
        return f"Guest@{contact.Club}" if contact.Club else "Guest"
    elif contact.Type in ['Member', 'Officer']:
        return contact.credentials or ''
    return ''


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


def load_setting(section, setting_key, default=None):
    """
    Loads a specific setting from a given section of settings.ini.
    """
    try:
        config = configparser.ConfigParser()
        # current_app.root_path points to the 'app' folder, so '../' goes to the project root
        settings_path = os.path.join(
            current_app.root_path, '..', 'settings.ini')

        if not os.path.exists(settings_path):
            print(f"Warning: settings.ini file not found at {settings_path}")
            return default

        config.read(settings_path)

        # .get() will return the value or None if not found, avoiding a crash
        return config.get(section, setting_key, fallback=default)

    except (configparser.NoSectionError, configparser.Error) as e:
        print(
            f"Error reading settings.ini (Section: {section}, Key: {setting_key}): {e}")
        return default


def load_all_settings():
    """
    Loads all sections and settings from settings.ini and returns them as a nested dict.
    """
    all_settings = {}
    try:
        config = configparser.ConfigParser()
        config.optionxform = str  # Preserve case
        # current_app.root_path points to the 'app' folder, so '../' goes to the project root
        settings_path = os.path.join(
            current_app.root_path, '..', 'settings.ini')

        if not os.path.exists(settings_path):
            print(f"Warning: settings.ini file not found at {settings_path}")
            return all_settings

        config.read(settings_path)

        for section in config.sections():
            # configparser keys are auto-lowercased when read.
            # Convert the section (which is a dict-like object) to a standard dict.
            all_settings[section] = dict(config[section])

        return all_settings

    except configparser.Error as e:
        print(f"Error reading settings.ini: {e}")
        return all_settings  # Return empty dict on error


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
    query_cols = [Meeting] if columns is None else columns
    
    # --- Mode 1: Simple Filter (if status_filter provided) ---
    if status_filter:
        query = db.session.query(*query_cols)\
            .filter(Meeting.status.in_(status_filter))\
            .join(SessionLog, Meeting.Meeting_Number == SessionLog.Meeting_Number)\
            .distinct()\
            .order_by(Meeting.Meeting_Number.desc())
            
        all_meetings = query.all()
        default_meeting_num = get_default_meeting_number()
        return all_meetings, default_meeting_num

    # --- Mode 2: Default Hybrid Active/Past Logic ---

    # Fetch active meetings ('unpublished', 'not started', or 'running')
    # Updated: Always include 'unpublished' so list is same for all users
    active_statuses = ['not started', 'running', 'unpublished']
        
    active_meetings = db.session.query(*query_cols)\
        .filter(Meeting.status.in_(active_statuses))\
        .order_by(Meeting.Meeting_Number.desc()).all()

    # Manager check removed as 'unpublished' is now always included

    active_meetings.sort(key=lambda m: m.Meeting_Number, reverse=True)

    # Fetch recent inactive meetings ('finished' or 'cancelled')
    past_meetings = db.session.query(*query_cols)\
        .filter(Meeting.status.in_(['finished', 'cancelled']))\
        .order_by(Meeting.Meeting_Number.desc()).limit(limit_past).all()

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
    running_meeting = Meeting.query.filter_by(status='running').first()
    if running_meeting:
        return running_meeting.Meeting_Number

    # 2. Check for next unfinished meeting (not started or unpublished)
    # Always include both statuses to ensure lower-numbered meetings are prioritized
    from .models import SessionLog
    upcoming_meeting = Meeting.query \
        .join(SessionLog, Meeting.Meeting_Number == SessionLog.Meeting_Number) \
        .filter(Meeting.status.in_(['not started', 'unpublished'])) \
        .order_by(Meeting.Meeting_Number.asc()) \
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
    if current_user.is_authenticated:
        user = current_user
        current_user_contact_id = user.Contact_ID
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


def get_excomm_team(all_settings):
    """
    Parses the [Excomm Team] section from settings.
    Returns a dictionary with 'name', 'term', and 'members' list.
    """
    raw_data = all_settings.get('Excomm Team', {})
    
    # Case-insensitive lookup for specific keys
    team_name = 'Unknown'
    term = 'Unknown'
    
    for k, v in raw_data.items():
        if k.lower() == 'excomm name':
            team_name = v
        elif k.lower() == 'term':
            term = v

    # Filter out the non-member keys (case-insensitive check)
    members = {
        k: v 
        for k, v in raw_data.items() 
        if k.lower() not in ['excomm name', 'term']
    }
    
    return {
        'name': team_name,
        'term': term,
        'members': members
    }

def get_meeting_types(all_settings):
    """
    Parses the [Meeting Types] section from settings.
    Example line in INI: Debate = 40, debate.csv, #D4F1F4, #000000
    Returns a dictionary compatible with Config.MEETING_TYPES.
    """
    raw_data = all_settings.get('Meeting Types', {})
    meeting_types = {}
    
    for title, value_str in raw_data.items():
        parts = [p.strip() for p in value_str.split(',')]
        if len(parts) >= 3:
            meeting_types[title] = {
                "template": parts[0],
                "background_color": parts[1],
                "foreground_color": parts[2]
            }
                
    # Sort meeting types alphabetically by title
    sorted_meeting_types = {k: meeting_types[k] for k in sorted(meeting_types.keys())}
    return sorted_meeting_types
    

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
        upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'profile_photos')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        img.save(file_path, "WEBP", quality=80)
        
        return f"uploads/profile_photos/{filename}"
    except Exception as e:
        print(f"Error processing avatar for contact {contact_id}: {e}")
        return None
