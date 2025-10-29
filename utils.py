# vpemaster/utils.py

from flask import current_app
from .models import Project  # Ensure Project model is imported if needed elsewhere
import re

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
    if not owner_contact or not owner_contact.Working_Path:
        return None # Cannot derive without owner or their working path

    pathway_mapping = current_app.config.get('PATHWAY_MAPPING', {})
    pathway_suffix = pathway_mapping.get(owner_contact.Working_Path)

    if not pathway_suffix:
        return None # Unknown pathway

    # Determine the role name from the log's session type
    role_name = None
    if hasattr(log, 'session_type') and log.session_type:
        role_name = log.session_type.Role
    elif hasattr(log, 'Type_ID'): # Fallback if session_type isn't loaded/available
        # This requires querying SessionType if not available on log,
        # adjust based on how log object is passed/constructed.
        # For simplicity, assuming session_type is usually available.
        # from .models import SessionType # Local import if needed
        # session_type = SessionType.query.get(log.Type_ID)
        # if session_type: role_name = session_type.Role
        pass # Add fallback query if necessary

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
        next_project_str = owner_contact.Next_Project
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

