from flask_login import login_required, current_user
from functools import wraps
from flask import abort, redirect, url_for, session

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
    
    # Resolve club_id from context early to avoid UnboundLocalError
    club_id = kwargs.get('club_id')
    meeting = kwargs.get('meeting')
    if not club_id and meeting:
        club_id = meeting.club_id
    if not club_id:
        club_id = session.get('current_club_id')
    
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

    # (ClubAdmin override removed to rely on database-driven permissions)

    # 2. Check for Sharing Master override
    meeting = kwargs.get('meeting')
    if meeting and meeting.sharing_master_id:
        # If user is the sharing master of this specific meeting
        user_contact_id = getattr(current_user, 'contact_id', None)
        if user_contact_id and user_contact_id == meeting.sharing_master_id:
            # Grant Operator-level permissions relevant to meeting management
            if target_perm in {
                'MEETING_MANAGE', 'MEMBERS_SELF', 'VOTING_VIEW_RESULTS', 
                'VOTING_TRACK_PROGRESS', 'ROSTER_EDIT', 'MEETING_VIEW_PUBLISHED', 'ROSTER_VIEW'
            }:
                return True
                
    # 4. Standard permission check via has_permission()
    # (Checks global roles assigned in user_roles table if no club override matches)
    
    # ENHANCEMENT: Auto-detect club context for standard checks
    if not club_id:
        from app.club_context import get_current_club_id
        club_id = get_current_club_id()

    if club_id:
        # Check permissions specifically within this club
        if hasattr(current_user, 'has_club_permission'):
            return current_user.has_club_permission(target_perm, club_id, **kwargs)
        return False
            
    # Fallback to global checks
    if hasattr(current_user, 'has_permission'):
        return current_user.has_permission(target_perm)

    return False


def club_permission_required(permission_name):
    """
    Decorator that requires a permission in the current club's context.

    Replacement for the (now-removed) ``@permission_required`` from
    ``app.auth.permissions``. That decorator consulted the cached
    Flask-Principal identity, which held the *global* permission set and
    therefore could not honor the per-club matrix. This decorator consults
    ``is_authorized`` (which routes through ``User.has_club_permission`` ->
    ``Role.has_permission(club_id)`` -> the per-club ``role_permissions``
    table).

    Failure semantics match the old ``@permission_required`` exactly:
        - Unauthenticated -> redirect to ``auth_bp.login``.
        - Authenticated but unauthorized -> ``abort(403)``.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_authorized(permission_name):
                if not current_user.is_authenticated:
                    return redirect(url_for('auth_bp.login'))
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

