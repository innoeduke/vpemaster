# vpemaster/utils.py

from flask import current_app
# Ensure Project model is imported if needed elsewhere
from .models import Project, Presentation, Meeting, SessionLog, Pathway, PathwayProject, Achievement
from . import db
import re
import configparser
import os
import hashlib
from sqlalchemy import distinct


def project_id_to_code(project_id, path_abbr):
    """
    Returns project code based on project_id and the two-letter path abbreviation.

    Args:
        project_id (int): The ID of the project
        path_abbr (str): Two-letter path abbreviation (e.g., 'PM', 'EH', 'DL')

    Returns:
        str: The project code with format <path_abbr><n.n(.n)> (e.g., "PM1.1", "EH3.2") or "" if not found
    """
    if not project_id:
        return ""

    # Handle generic project
    if project_id == 60:
        return "TM1.0"

    # For other projects, path_abbr is required
    if not path_abbr:
        return ""

    # Special handling for presentations
    presentation_series_initials = {
        'Successful Club Series': 'SC',
        'Leadership Excellence Series': 'LE',
        'Better Speaker Series': 'BS'
    }

    if path_abbr in presentation_series_initials.values():
        presentation = Presentation.query.get(project_id)
        if presentation and presentation.series:
            series_name = next((name for name, initial in presentation_series_initials.items(
            ) if initial == path_abbr), None)
            if series_name and presentation.series == series_name:
                return f"{path_abbr}{presentation.code}"
        return ""

    project = Project.query.get(project_id)
    if not project:
        return ""

    pathway = db.session.query(Pathway).filter_by(abbr=path_abbr).first()
    if not pathway:
        return ""

    pathway_project = db.session.query(PathwayProject).filter_by(
        path_id=pathway.id, project_id=project_id).first()

    if pathway_project:
        return f"{path_abbr}{pathway_project.code}"

    return ""


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
    project_specific_roles = ["Prepared Speaker", "Individual Evaluator"]
    if role_name in project_specific_roles and log.Project_ID:
        # Check if the project object is already loaded/available on the log object
        project = None
        if hasattr(log, 'project') and log.project:
            project = log.project
        else:
            # Fetch the project if not readily available
            project = Project.query.get(log.Project_ID)

        if not project:
            return None

        pathway_project = db.session.query(PathwayProject).filter_by(
            path_id=pathway.id, project_id=project.id).first()

        if pathway_project:
            # Return the full specific project code (e.g., "PM1.1")
            return f"{pathway_suffix}{pathway_project.code}"

    # --- Priority 2: Other roles - Use highest level achievement + 1 ---
    else:
        # Query for the highest level completion achievement in the current path
        highest_achievement = Achievement.query.filter_by(
            contact_id=owner_contact.id,
            path_name=owner_contact.Current_Path,
            achievement_type='level-completion'
        ).order_by(Achievement.level.desc()).first()
        
        current_level = 1
        if highest_achievement:
            # If level L is completed, the current work is for level L+1 (capped at 5)
            current_level = min(highest_achievement.level + 1, 5)
            
        return f"{pathway_suffix}{current_level}"

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

    # Fetch active meetings ('not started' or 'running')
    active_meetings = db.session.query(*query_cols)\
        .filter(Meeting.status.in_(['not started', 'running']))\
        .order_by(Meeting.Meeting_Number.desc()).all()

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
    upcoming_meeting = Meeting.query \
        .filter(Meeting.status == 'not started') \
        .order_by(Meeting.Meeting_Date.asc(), Meeting.Meeting_Number.asc()) \
        .first()
    
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
                
    return meeting_types
