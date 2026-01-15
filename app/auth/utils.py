from flask_login import login_required, current_user
from functools import wraps
from flask import redirect, url_for, session

# Guest permissions for unauthenticated users
# Guest permissions are now handled via Database Role 'Guest' and AnonymousUser

def is_authorized(user_role_or_permission, permission=None, **kwargs):
    """
    Checks if a user/role is authorized for a feature.
    
    Updated to use database-backed permission system.
    
    Usage 1 (Current User): is_authorized('AGENDA_EDIT') -> checks current_user
    Usage 2 (Context-aware): is_authorized('AGENDA_EDIT', meeting=selected_meeting)
    """
    
    # Check for Meeting Manager override
    meeting = kwargs.get('meeting')
    target_perm = permission if permission else user_role_or_permission
    
    if meeting and current_user.is_authenticated:
        # If user is the manager of this specific meeting
        if hasattr(current_user, 'Contact_ID') and current_user.Contact_ID == meeting.manager_id:
            # Grant Operator-level permissions relevant to meeting management
            # Specifically Agenda Edit and Booking management
            if target_perm in {'AGENDA_EDIT', 'BOOKING_ASSIGN_ALL', 'BOOKING_BOOK_OWN', 'VOTING_VIEW_RESULTS', 'VOTING_TRACK_PROGRESS'}:
                return True

    # Usage 1: Check current user logic (PRIMARY USE CASE)
    if permission is None:
        # Argument is the permission name
        perm_name = user_role_or_permission
        # Both Authenticated and Anonymous users now have has_permission() method
        # (AnonymousUser loads from 'Guest' role in DB)
        if hasattr(current_user, 'has_permission'):
            return current_user.has_permission(perm_name)
        return False

    # Usage 2: Explicit role check (Legacy support - DEPRECATED)
    # This is rarely used and should be removed after full migration
    if hasattr(current_user, 'has_permission'):
        return current_user.has_permission(permission)
    
    return False
