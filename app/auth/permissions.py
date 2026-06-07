"""Permission utilities for Flask-Principal integration."""
from functools import wraps
from flask import abort
from flask_principal import Permission as PrincipalPermission, RoleNeed
from flask_login import current_user


class PermissionNeed(tuple):
    """A need for a specific permission."""
    def __new__(cls, permission_name):
        return tuple.__new__(cls, ('permission', permission_name))


def create_permission(permission_name):
    """Create a Flask-Principal Permission object for a permission name."""
    return PrincipalPermission(PermissionNeed(permission_name))


def create_role_permission(role_name):
    """Create a Flask-Principal Permission object for a role."""
    return PrincipalPermission(RoleNeed(role_name))


def role_required(role_name):
    """
    Decorator to require a specific role for a route.
    
    Usage:
        @role_required('Admin')
        def admin_only():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            permission = create_role_permission(role_name)
            if not permission.can():
                if not current_user.is_authenticated:
                    from flask import redirect, url_for
                    return redirect(url_for('auth_bp.login'))
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def any_permission_required(*permission_names):
    """
    Decorator to require ANY of the specified permissions.
    
    Usage:
        @any_permission_required('MEETING_MANAGE', 'MEETING_VIEW_PUBLISHED')
        def view_or_edit_agenda():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            for perm_name in permission_names:
                permission = create_permission(perm_name)
                if permission.can():
                    return f(*args, **kwargs)
            
            if not current_user.is_authenticated:
                from flask import redirect, url_for
                return redirect(url_for('auth_bp.login'))
            abort(403)
        return decorated_function
    return decorator


def all_permissions_required(*permission_names):
    """
    Decorator to require ALL of the specified permissions.
    
    Usage:
        @all_permissions_required('MEETING_VIEW_PUBLISHED', 'MEMBERS_SELF')
        def view_combined():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            for perm_name in permission_names:
                permission = create_permission(perm_name)
                if not permission.can():
                    if not current_user.is_authenticated:
                        from flask import redirect, url_for
                        return redirect(url_for('auth_bp.login'))
                    abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# Export commonly used permissions as constants
class Permissions:
    """Centralized permission constants."""
    # Settings (Category: settings)
    SETTINGS_VIEW = 'SETTINGS_VIEW'
    SETTINGS_EDIT = 'SETTINGS_EDIT'
    MEDIA_MANAGE = 'MEDIA_MANAGE'

    # Meeting & Booking (Category: meeting)
    MEETING_VIEW_PUBLISHED = 'MEETING_VIEW_PUBLISHED'
    MEETING_VIEW_ALL = 'MEETING_VIEW_ALL'
    MEETING_CREATE = 'MEETING_CREATE'
    MEETING_MANAGE = 'MEETING_MANAGE'
    VOTING_VIEW_RESULTS = 'VOTING_VIEW_RESULTS'
    VOTING_TRACK_PROGRESS = 'VOTING_TRACK_PROGRESS'

    # Members (Category: members)
    MEMBERS_MANAGE = 'MEMBERS_MANAGE'
    MEMBERS_SELF = 'MEMBERS_SELF'
    SPEECH_LOGS_MANAGE = 'SPEECH_LOGS_MANAGE'

    # Roster & Contacts (Category: roster)
    ROSTER_VIEW = 'ROSTER_VIEW'
    ROSTER_EDIT = 'ROSTER_EDIT'

    # Tools (Category: tools)
    LIBRARY_VIEW = 'LIBRARY_VIEW'
    LUCKY_DRAW_EDIT = 'LUCKY_DRAW_EDIT'
    UPLOAD_MANAGE = 'UPLOAD_MANAGE'
    ISSUE_MANAGE = 'ISSUE_MANAGE'

    # Chat & AI (Category: chat)
    CHAT_COMMANDS = 'CHAT_COMMANDS'
    CHAT_AI = 'CHAT_AI'

    # Roles
    SYSADMIN = 'SysAdmin'
    CLUBADMIN = 'ClubAdmin'
    OPERATOR = 'Operator'
    STAFF = 'Staff'
    USER = 'Member'
