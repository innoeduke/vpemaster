# vpemaster/utils.py

from flask import current_app
# Ensure Project model is imported if needed elsewhere
from .models import Project, Presentation
import re
import configparser
import os
import hashlib


def project_id_to_code(project_id, path_abbr):
    """
    Returns project code based on project_id and the two-letter path abbreviation.

    Args:
        project_id (int): The ID of the project
        path_abbr (str): Two-letter path abbreviation (e.g., 'PM', 'EH', 'DL')

    Returns:
        str: The project code with format <path_abbr><n.n(.n)> (e.g., "PM1.1", "EH3.2") or "" if not found
    """
    if not project_id or not path_abbr:
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

    # Special case for project ID 60 (TM1.0)
    if project_id == 60:
        return "TM1.0"

    code_attr = f"Code_{path_abbr}"
    project_code = getattr(project, code_attr, None)

    if project_code:
        return f"{path_abbr}{project_code}"
    return ""


def derive_current_path_level(log, owner_contact):
    """
    Derives the 'current_path_level' based on the role, project, and owner's pathway.
    - For Speakers/Evaluators with a linked project, returns the specific project code (e.g., PM1.1).
    - For other roles, returns the general level code from the owner's Next_Project (e.g., PM5).
    - Returns None if insufficient information is available.

    Args:
        log (SessionLog or similar object): The session log object. Must have attributes like
                                             Project_ID, Type_ID, and potentially session_type and project
                                             (or these relationships should be loaded).
        owner_contact (Contact): The Contact object of the person assigned to the role.

    Returns:
        str or None: The derived current_path_level string or None.
    """
    user = owner_contact.user if owner_contact else None
    if not user or not user.Current_Path:
        return None  # Cannot derive without owner or their working path

    pathway_mapping = current_app.config.get('PATHWAY_MAPPING', {})
    pathway_suffix = pathway_mapping.get(user.Current_Path)

    if not pathway_suffix:
        return None  # Unknown pathway

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

        if project:
            project_code_attr = f"Code_{pathway_suffix}"
            project_code_val = getattr(project, project_code_attr, None)
            if project_code_val:
                # Return the full specific project code (e.g., "PM1.1")
                return f"{pathway_suffix}{project_code_val}"

    # --- Priority 2: Other roles - Use general level from Next_Project ---
    else:
        next_project_str = user.Next_Project
        if next_project_str:
            # Use regex to extract only the Path + Level part (e.g., PM5 from PM5.2)
            match = re.match(r"([A-Z]+)(\d+)", next_project_str)
            if match:
                path_abbr = match.group(1)
                level_num = match.group(2)
                # Ensure the extracted path matches the user's working path for consistency
                if path_abbr == pathway_suffix:
                    # Return just the path and level (e.g., "PM5")
                    return f"{path_abbr}{level_num}"

    # --- Fallback ---
    return None


def derive_credentials(contact):
    """
    Derives the credentials string for a given contact.
    - Returns an empty string for DTMs.
    - Formats for Guests (e.g., "Guest@Club").
    - Formats for Members based on completed levels (e.g., "PM1/DL2").
    - Returns an empty string if the contact is None or has no specific credentials.
    """
    if not contact:
        return ''

    if contact.DTM:
        return 'DTM'
    elif contact.Type == 'Guest':
        return f"Guest@{contact.Club}" if contact.Club else "Guest"
    elif contact.Type in ['Member', 'Officer'] and contact.user and contact.user.credentials:
        return contact.user.credentials
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