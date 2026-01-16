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

    # Import models here to avoid circular dependencies
    from app.models import AuthRole, UserClub
    from app.auth.permissions import Permissions

    # 1. SysAdmin Override: Full access to all resources/actions of all clubs
    # Retrieval from user_clubs as per requirement
    sys_role = AuthRole.get_by_name(Permissions.ADMIN)
    if sys_role:
        # If user has SysAdmin role in ANY club entry in user_clubs, they are a SysAdmin
        is_sysadmin = UserClub.query.filter_by(user_id=current_user.id, club_role_id=sys_role.id).first()
        if is_sysadmin:
            return True

    # 2. ClubAdmin Override: Full access to owned clubs
    club_role = AuthRole.get_by_name(Permissions.OPERATOR)
    if club_role:
        # Resolve club_id from context
        club_id = kwargs.get('club_id')
        meeting = kwargs.get('meeting')
        if not club_id and meeting:
            club_id = meeting.club_id
        if not club_id:
            club_id = session.get('current_club_id')
        
        if club_id:
            is_clubadmin = UserClub.query.filter_by(
                user_id=current_user.id, 
                club_id=club_id, 
                club_role_id=club_role.id
            ).first()
            if is_clubadmin:
                return True

    # 3. Check for Meeting Manager override
    meeting = kwargs.get('meeting')
    if meeting:
        # If user is the manager of this specific meeting
        if hasattr(current_user, 'Contact_ID') and current_user.Contact_ID == meeting.manager_id:
            # Grant Operator-level permissions relevant to meeting management
            # Specifically Agenda Edit and Booking management
            if target_perm in {'AGENDA_EDIT', 'BOOKING_ASSIGN_ALL', 'BOOKING_BOOK_OWN', 'VOTING_VIEW_RESULTS', 'VOTING_TRACK_PROGRESS'}:
                return True

    # 4. Standard permission check via has_permission()
    # (Checks global roles assigned in user_roles table if no club override matches)
    if hasattr(current_user, 'has_permission'):
        return current_user.has_permission(target_perm)
    
    return False

