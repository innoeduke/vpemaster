from flask_login import login_required, current_user
from functools import wraps
from flask import redirect, url_for, session

# Guest permissions for unauthenticated users
# Guest permissions are now handled via Database Role 'Guest' and AnonymousUser

def is_authorized(user_role_or_permission, permission=None, **kwargs):
    """
    Checks if a user/role is authorized for a feature.
    
    Updated to use database-backed permission system and multi-club support.
    
    Usage 1 (Current User): is_authorized('AGENDA_EDIT') -> checks current_user
    Usage 2 (Context-aware): is_authorized('AGENDA_EDIT', meeting=selected_meeting)
    """
    
    # Target permission to check
    target_perm = permission if permission else user_role_or_permission
    
    if not current_user.is_authenticated:
        # Both Authenticated and Anonymous users now have has_permission() method
        if hasattr(current_user, 'has_permission'):
            return current_user.has_permission(target_perm)
        return False

    # Imports inside function to avoid circular dependency
    from app.auth.permissions import Permissions

    # 1. SysAdmin Override: Full access to all resources/actions of all clubs
    # Relies on the helper method on User model
    if hasattr(current_user, 'is_sysadmin') and current_user.is_sysadmin:
        return True

    # 2. ClubAdmin Override: Full access to owned clubs (except strictly SysAdmin-only features)
    if target_perm != Permissions.SYSADMIN:
        # Resolve club_id from context
        club_id = kwargs.get('club_id')
        meeting = kwargs.get('meeting')
        if not club_id and meeting:
            club_id = meeting.club_id
        if not club_id:
            club_id = session.get('current_club_id')
        
        # Use helper method on User model
        if hasattr(current_user, 'is_club_admin') and current_user.is_club_admin(club_id):
            return True

    # 3. Check for Meeting Manager override
    meeting = kwargs.get('meeting')
    if meeting:
        # If user is the manager of this specific meeting
        if hasattr(current_user, 'contact_id') and current_user.contact_id == meeting.manager_id:
            # Grant Operator-level permissions relevant to meeting management
            # Specifically Agenda Edit and Booking management
            if target_perm in {'AGENDA_EDIT', 'BOOKING_ASSIGN_ALL', 'BOOKING_BOOK_OWN', 'VOTING_VIEW_RESULTS', 'VOTING_TRACK_PROGRESS'}:
                return True

    # 4. Standard permission check via has_permission()
    # (Checks global roles assigned in user_roles table if no club override matches)
    if hasattr(current_user, 'has_permission'):
        return current_user.has_permission(target_perm)
    
    return False

