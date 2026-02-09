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


def permission_required(permission_name):
    """
    Decorator to require a specific permission for a route.
    
    Usage:
        @permission_required('AGENDA_EDIT')
        def edit_agenda():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            permission = create_permission(permission_name)
            if not permission.can():
                if not current_user.is_authenticated:
                    from flask import redirect, url_for
                    return redirect(url_for('auth_bp.login'))
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


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
        @any_permission_required('AGENDA_EDIT', 'AGENDA_VIEW')
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
        @all_permissions_required('AGENDA_VIEW', 'BOOKING_VIEW')
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
    AGENDA_EDIT = 'AGENDA_EDIT'
    AGENDA_VIEW = 'AGENDA_VIEW'
    BOOKING_ASSIGN_ALL = 'BOOKING_ASSIGN_ALL'
    BOOKING_BOOK_OWN = 'BOOKING_BOOK_OWN'
    SPEECH_LOGS_EDIT_ALL = 'SPEECH_LOGS_EDIT_ALL'
    SPEECH_LOGS_VIEW_ALL = 'SPEECH_LOGS_VIEW_ALL'
    SPEECH_LOGS_VIEW_OWN = 'SPEECH_LOGS_VIEW_OWN'
    PATHWAY_LIB_EDIT = 'PATHWAY_LIB_EDIT'
    PATHWAY_LIB_VIEW = 'PATHWAY_LIB_VIEW'
    PROFILE_OWN = 'PROFILE_OWN'
    PROFILE_VIEW = 'PROFILE_VIEW'
    PROFILE_EDIT = 'PROFILE_EDIT'
    LUCKY_DRAW_VIEW = 'LUCKY_DRAW_VIEW'
    LUCKY_DRAW_EDIT = 'LUCKY_DRAW_EDIT'
    CONTACT_BOOK_EDIT = 'CONTACT_BOOK_EDIT'
    CONTACT_BOOK_VIEW = 'CONTACT_BOOK_VIEW'
    SETTINGS_EDIT_ALL = 'SETTINGS_EDIT_ALL'
    SETTINGS_VIEW_ALL = 'SETTINGS_VIEW_ALL'
    ACHIEVEMENTS_EDIT = 'ACHIEVEMENTS_EDIT'
    ACHIEVEMENTS_VIEW = 'ACHIEVEMENTS_VIEW'
    VOTING_VIEW_RESULTS = 'VOTING_VIEW_RESULTS'
    VOTING_TRACK_PROGRESS = 'VOTING_TRACK_PROGRESS'
    ROSTER_VIEW = 'ROSTER_VIEW'
    ROSTER_EDIT = 'ROSTER_EDIT'
    ABOUT_CLUB_VIEW = 'ABOUT_CLUB_VIEW'
    ABOUT_CLUB_EDIT = 'ABOUT_CLUB_EDIT'
    CLUBS_MANAGE = 'CLUBS_MANAGE'
    MEDIA_ACCESS = 'MEDIA_ACCESS'
    RESET_PASSWORD_CLUB = 'RESET_PASSWORD_CLUB'
    CONTACTS_MEMBERS_VIEW = 'CONTACTS_MEMBERS_VIEW'
    
    # Roles
    SYSADMIN = 'SysAdmin'
    CLUBADMIN = 'ClubAdmin'
    STAFF = 'Staff'
    USER = 'User'
