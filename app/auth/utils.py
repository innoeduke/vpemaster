from flask import redirect, url_for, session
from functools import wraps

# A single, centralized map of all permissions in the application.
# We use sets for very fast "in" lookups.
ROLE_PERMISSIONS = {
    "Admin": {
        "AGENDA_EDIT",
        "BOOKING_ASSIGN_ALL",
        "SPEECH_LOGS_EDIT_ALL",
        "PATHWAY_LIB_EDIT",
        "CONTACT_BOOK_EDIT",
        "SETTINGS_EDIT_ALL",
    },
    "VPE": {
        "AGENDA_EDIT",
        "BOOKING_ASSIGN_ALL",
        "SPEECH_LOGS_EDIT_ALL",
        "PATHWAY_LIB_EDIT",
        "CONTACT_BOOK_EDIT",
        "SETTINGS_VIEW_ALL",
    },
    "Meeting Manager": {
        "AGENDA_EDIT",
        "BOOKING_ASSIGN_ALL",
        "SPEECH_LOGS_VIEW_OWN",
        "PATHWAY_LIB_VIEW",
        "CONTACT_BOOK_EDIT",
    },
    "Officer": {
        "AGENDA_VIEW",
        "BOOKING_BOOK_OWN",
        "SPEECH_LOGS_VIEW_OWN",
        "CONTACT_BOOK_VIEW",
        "PATHWAY_LIB_VIEW",
    },
    "Member": {
        "AGENDA_VIEW",
        "BOOKING_BOOK_OWN",
        "SPEECH_LOGS_VIEW_OWN",
        "PATHWAY_LIB_VIEW",
    },
    "Guest": {
        "AGENDA_VIEW",
        "PATHWAY_LIB_VIEW",
    }
}

# Add "view" permissions for roles that have "edit"
for role, perms in ROLE_PERMISSIONS.items():
    if "AGENDA_EDIT" in perms:
        perms.add("AGENDA_VIEW")
    if "BOOKING_ASSIGN_ALL" in perms:
        perms.add("BOOKING_BOOK_OWN")
    if "CONTACT_BOOK_EDIT" in perms:
        perms.add("CONTACT_BOOK_VIEW")
    if "SPEECH_LOGS_EDIT_ALL" in perms:
        perms.add("SPEECH_LOGS_VIEW_ALL")
    if "PATHWAY_LIB_EDIT" in perms:
        perms.add("PATHWAY_LIB_VIEW")
    if "SETTINGS_EDIT_ALL" in perms:
        perms.add("SETTINGS_VIEW_ALL")


def is_authorized(user_role, feature):
    """
    Central function to check if a user role is authorized for a feature.
    """
    if user_role is None:
        user_role = "Guest"

    # Get the set of permissions for the given role, or an empty set if role doesn't exist
    permissions = ROLE_PERMISSIONS.get(user_role, set())

    # Return True if the feature is in their permissions, False otherwise
    return feature in permissions

# Decorator to check if user is logged in


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('auth_bp.login'))
        return f(*args, **kwargs)
    return decorated_function
