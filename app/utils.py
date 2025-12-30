# vpemaster/utils.py

from flask import current_app
# Ensure Project model is imported if needed elsewhere
from .models import Project, Meeting, SessionLog, Pathway, PathwayProject, Achievement, Contact
from . import db
import re
import configparser
import os
import hashlib
from sqlalchemy import distinct


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
    contact = Contact.query.get(contact_id)
    if not contact:
        return None

    recalculate_contact_metadata(contact)

    db.session.add(contact)
    db.session.commit()
    return contact


def derive_current_path_level(log, owner_contact):
    """
    Derives the 'current_path_level' based on the role, project, and owner's pathway.
    - For Speakers/Evaluators with a linked project, returns the specific project code (e.g., PM1.1).
    - For other roles, returns the general level code by checking the highest achievement (e.g., PM2 if L1 is done).
    - Returns None if insufficient information is available.

    Args:
        log (SessionLog or similar object): The session log object. Must have attributes like
                                             Project_ID, Type_ID, and potentially session_type and project
                                             (or these relationships should be loaded).
        owner_contact (Contact): The Contact object of the person assigned to the role.

    Returns:
        str or None: The derived current_path_level string or None.
    """
    if not owner_contact or not owner_contact.Current_Path:
        return None  # Cannot derive without owner or their working path

    pathway = db.session.query(Pathway).filter_by(name=owner_contact.Current_Path).first()

    if not pathway:
        return None  # Unknown pathway

    pathway_suffix = pathway.abbr

    # Determine the role name from the log's session type
    role_name = None
    if hasattr(log, 'session_type') and log.session_type and log.session_type.role:
        role_name = log.session_type.role.name
    elif hasattr(log, 'Type_ID'):  # Fallback if session_type isn't loaded/available
        # This requires querying SessionType if not available on log,
        # adjust based on how log object is passed/constructed.
        # For simplicity, assuming session_type is usually available.
        # from .models import SessionType # Local import if needed
        # session_type = SessionType.query.get(log.Type_ID)
        # if session_type: role_name = session_type.role.name
        pass  # Add fallback query if necessary

    # --- Priority 1: Speaker/Evaluator with Project ID ---
    # Check if the role is typically associated with a specific project completion
    project_specific_roles = ["Prepared Speaker", "Individual Evaluator", "Presenter"]
    if role_name in project_specific_roles and log.Project_ID:
        code = get_project_code(log.Project_ID, owner_contact.Current_Path)
        if code:
            return code

    # --- Priority 2: Other roles - Use highest level achievement + 1 ---
    else:
        # Determine base level from contact.credentials for consistency
        start_level = 1
        if owner_contact.credentials:
            # Match the current path abbreviation followed by a level number
            match = re.match(rf"^{pathway_suffix}(\d+)$", owner_contact.credentials.strip().upper())
            if match:
                level_achieved = int(match.group(1))
                # If level L is completed, the current work is for level L+1 (capped at 5)
                start_level = min(level_achieved + 1, 5)
            
        return f"{pathway_suffix}{start_level}"

    # --- Fallback ---
    return None


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


def get_meetings_by_status(limit_past=8, columns=None):
    """
    Fetches meetings, categorizing them as 'active' or 'past' based on status.

    Args:
        limit_past (int): The maximum number of past meetings to retrieve.
        columns (list): A list of specific Meeting columns to query. 
                        If None, queries the full Meeting object.

    Returns:
        tuple: (all_meetings, default_meeting_num)
               - all_meetings: A sorted list of meeting objects or tuples.
               - default_meeting_num: The number of the soonest 'not started' meeting.
    """
    query_cols = [Meeting] if columns is None else columns

    # Fetch active meetings ('unpublished', 'not started', or 'running')
    active_statuses = ['not started', 'running']
    try:
        from flask_login import current_user
        if current_user.is_authenticated and current_user.is_officer:
            active_statuses.append('unpublished')
    except Exception:
        # Not in a request context or other issue
        pass
        
    active_meetings = db.session.query(*query_cols)\
        .filter(Meeting.status.in_(active_statuses))\
        .order_by(Meeting.Meeting_Number.desc()).all()

    # Also include unpublished meetings if current user is the manager
    try:
        from flask_login import current_user
        if current_user.is_authenticated and current_user.Contact_ID:
            manager_meetings = db.session.query(*query_cols)\
                .filter(Meeting.status == 'unpublished')\
                .filter(Meeting.manager_id == current_user.Contact_ID)\
                .all()
            # deduplicate
            existing_nums = {m.Meeting_Number for m in active_meetings}
            for m in manager_meetings:
                if m.Meeting_Number not in existing_nums:
                    active_meetings.append(m)
    except Exception:
        pass

    active_meetings.sort(key=lambda m: m.Meeting_Number, reverse=True)

    # Fetch recent inactive meetings ('finished' or 'cancelled')
    past_meetings = db.session.query(*query_cols)\
        .filter(Meeting.status.in_(['finished', 'cancelled']))\
        .order_by(Meeting.Meeting_Number.desc()).limit(limit_past).all()

    # Combine and sort all meetings by meeting number
    all_meetings = sorted(active_meetings + past_meetings,
                          key=lambda m: m.Meeting_Number, reverse=True)

    # Filter meetings to only those that have session logs
    meetings_with_logs_subquery = db.session.query(
        distinct(SessionLog.Meeting_Number)).subquery()
    all_meetings = [m for m in all_meetings if m.Meeting_Number in [
        row[0] for row in db.session.query(meetings_with_logs_subquery).all()]]

    return all_meetings


def get_default_meeting_number():
    """
    Determines the default meeting number based on priority:
    1. 'running' meeting
    2. Soonest 'not started' meeting
    Returns None if neither is found.
    """
    # 1. Check for running meeting
    running_meeting = Meeting.query.filter_by(status='running').first()
    if running_meeting:
        return running_meeting.Meeting_Number

    # 2. Check for next not-started meeting
    upcoming_priority_statuses = ['not started']
    try:
        from flask_login import current_user
        if current_user.is_authenticated and current_user.is_officer:
            upcoming_priority_statuses.append('unpublished')
    except Exception:
        pass
    from .models import SessionLog
    upcoming_meeting = Meeting.query \
        .join(SessionLog, Meeting.Meeting_Number == SessionLog.Meeting_Number) \
        .filter(Meeting.status.in_(upcoming_priority_statuses)) \
        .order_by(Meeting.Meeting_Date.asc(), Meeting.Meeting_Number.asc()) \
        .first()
    
    # If no meeting found, check if user is a manager of an unpublished meeting
    if not upcoming_meeting:
        try:
            from flask_login import current_user
            if current_user.is_authenticated and current_user.Contact_ID:
                upcoming_meeting = Meeting.query \
                    .join(SessionLog, Meeting.Meeting_Number == SessionLog.Meeting_Number) \
                    .filter(Meeting.status == 'unpublished') \
                    .filter(Meeting.manager_id == current_user.Contact_ID) \
                    .order_by(Meeting.Meeting_Date.asc()) \
                    .first()
        except Exception:
            pass

    if upcoming_meeting:
        return upcoming_meeting.Meeting_Number
    
    return None


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
