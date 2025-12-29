from flask_login import login_required, current_user
from functools import wraps
from flask import redirect, url_for, session

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
        "ACHIEVEMENTS_EDIT",
    },
    "VPE": {
        "AGENDA_EDIT",
        "BOOKING_ASSIGN_ALL",
        "SPEECH_LOGS_EDIT_ALL",
        "PATHWAY_LIB_EDIT",
        "CONTACT_BOOK_EDIT",
        "SETTINGS_VIEW_ALL",
        "ACHIEVEMENTS_EDIT",
    },
    "Officer": {
        "AGENDA_VIEW",
        "BOOKING_BOOK_OWN",
        "SPEECH_LOGS_VIEW_ALL",
        "CONTACT_BOOK_VIEW",
        "PATHWAY_LIB_VIEW",
        "ACHIEVEMENTS_VIEW",
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
    if "ACHIEVEMENTS_EDIT" in perms:
        perms.add("ACHIEVEMENTS_VIEW")


def is_authorized(user_role_or_permission, permission=None, **kwargs):
    """
    Checks if a user/role is authorized for a feature.
    
    Usage 1 (Legacy/Role-based): is_authorized('Admin', 'AGENDA_EDIT')
    Usage 2 (Current User): is_authorized('AGENDA_EDIT') -> checks current_user
    Usage 3 (Context-aware): is_authorized('AGENDA_EDIT', meeting=selected_meeting)
    """
    
    # Check for Meeting Manager override
    meeting = kwargs.get('meeting')
    target_perm = permission if permission else user_role_or_permission
    
    if meeting and current_user.is_authenticated:
        # If user is the manager of this specific meeting
        if hasattr(current_user, 'Contact_ID') and current_user.Contact_ID == meeting.manager_id:
            # Grant VPE-level permissions relevant to meeting management
            # Specifically Agenda Edit and Booking management
            if target_perm in {'AGENDA_EDIT', 'BOOKING_ASSIGN_ALL', 'BOOKING_BOOK_OWN'}:
                return True

    # Usage 2: Check current user logic
    if permission is None:
        # Argument is the permission name
        perm_name = user_role_or_permission
        if current_user.is_authenticated:
            return current_user.can(perm_name)
        else:
            # Guest check
            return perm_name in ROLE_PERMISSIONS.get("Guest", set())

    # Usage 1: Explicit role check (Legacy support)
    user_role = user_role_or_permission
    if user_role is None:
        user_role = "Guest"

    permissions = ROLE_PERMISSIONS.get(user_role, set())
    return permission in permissions
