"""Club context utilities for multi-club support."""
from flask import session, g
from functools import wraps


def get_current_club_id():
    """
    Get the current club ID from session.
    
    Returns:
        int: Current club ID or None if not set
    """
    from flask import has_request_context
    if not has_request_context():
        return None
    return session.get('current_club_id')


def set_current_club_id(club_id):
    """
    Set the current club ID in session.
    
    Args:
        club_id (int): Club ID to set as current
    """
    session['current_club_id'] = club_id


# Sentinel used to distinguish "not yet resolved" from "resolved to None".
_MISSING = object()


def get_or_set_default_club():
    """
    Get current club ID or set to default if not set.

    Returns:
        int: Current club ID
    """
    from flask import request, has_request_context

    if has_request_context():
        cached = getattr(request, '_club_id_resolved', _MISSING)
        if cached is not _MISSING:
            return cached

    club_id = _resolve_club_id()

    if has_request_context():
        request._club_id_resolved = club_id
    return club_id


def _resolve_club_id():
    """Inner helper to perform the actual club ID resolution."""
    from flask import request, has_request_context

    # 0. Check request arguments (e.g., from redirection query param) FIRST
    # If explicitly passed via URL, this should override session context.
    try:
        url_club_id = request.args.get('club_id')
        if url_club_id:
            club_id = int(url_club_id)
            set_current_club_id(club_id)
            return club_id
    except (ValueError, TypeError):
        pass

    # If the request is rendering the club directory, do not auto-restore
    # a default club context — the directory is a global view.
    if has_request_context() and getattr(g, 'in_club_directory', False):
        return session.get('current_club_id')

    from app.models import Club
    club_id = get_current_club_id()

    # If club_id is set in session, VALIDATE it for the current authenticated user
    if club_id:
        from flask_login import current_user
        if current_user.is_authenticated:
            # SysAdmin bypass: Allow SysAdmin to maintain ANY club context
            if current_user.is_sysadmin:
                return club_id

            from app.models import UserClub
            user_club = UserClub.query.filter_by(user_id=current_user.id, club_id=club_id).first()

            if not user_club:
                # Invalid context for this regular user! Clear it.
                club_id = None
                session.pop('current_club_id', None)

    if not club_id:
        # Try to get user's primary/home club
        from flask_login import current_user
        if current_user.is_authenticated:
            from app.models import UserClub
            home_uc = UserClub.query.filter_by(user_id=current_user.id, is_home=True).first()
            if home_uc:
                set_current_club_id(home_uc.club_id)
                return home_uc.club_id

            # Fallback to any club membership
            any_uc = UserClub.query.filter_by(user_id=current_user.id).first()
            if any_uc:
                set_current_club_id(any_uc.club_id)
                return any_uc.club_id

        # Fallback to first club
        default_club = Club.query.first()
        if default_club:
            set_current_club_id(default_club.id)
            return default_club.id

    return club_id



def require_club_context(f):
    """
    Decorator to ensure club context is set before executing route.
    
    Usage:
        @app.route('/meetings')
        @require_club_context
        def meetings():
            club_id = get_current_club_id()
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        get_or_set_default_club()
        return f(*args, **kwargs)
    return decorated_function


def filter_by_club(query, model_class):
    """
    Add club filter to a query.
    
    Args:
        query: SQLAlchemy query object
        model_class: Model class that has club_id attribute
        
    Returns:
        Filtered query
        
    Usage:
        query = Meeting.query
        query = filter_by_club(query, Meeting)
    """
    club_id = get_current_club_id()
    if club_id and hasattr(model_class, 'club_id'):
        return query.filter(model_class.club_id == club_id)
    return query


def get_user_clubs(user):
    """
    Get all clubs a user belongs to.
    
    Args:
        user: User object
        
    Returns:
        List of Club objects
    """
    if not user:
        return []
    
    from app.models import Club, UserClub
    club_ids = [uc.club_id for uc in UserClub.query.filter_by(user_id=user.id).all()]
    return Club.query.filter(Club.id.in_(club_ids)).all() if club_ids else []


def switch_club(club_id):
    """
    Switch to a different club context.
    
    Args:
        club_id (int): ID of club to switch to
        
    Returns:
        bool: True if successful, False otherwise
    """
    from app.models import Club
    
    club = db.session.get(Club, club_id)
    if club:
        set_current_club_id(club_id)
        return True
    return False


def authorized_club_required(f):
    """
    Decorator to ensure the user is authorized for the current club context.
    
    1. Ensures club context is set.
    2. For authenticated users:
       - SysAdmin: Can access any club
       - ClubAdmin: Can access clubs where they are an ExComm officer
       - Other users: Must have a membership record for the current club
    3. For anonymous users: Allows access if they have MEETING_VIEW_PUBLISHED permission.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask_login import current_user
        from flask import abort, redirect, url_for
        from app.auth.permissions import Permissions
        from app.models import UserClub

        # Ensure club context is established
        club_id = get_or_set_default_club()
        if not club_id:
            abort(404, description="No club context found")

        # SysAdmin bypass — global access to every club
        if current_user.is_authenticated and current_user.is_sysadmin:
            return f(*args, **kwargs)

        # Membership-row bypass: any authenticated user with a UserClub row
        # for this club is granted access. This is the relaxed "any valid
        # membership record grants access" rule that keeps the per-club
        # permission matrix from being a hard gate for actual members of
        # the club (e.g. the super club has no per-club matrix by design,
        # but Memory Maker users still need to reach the settings page).
        if current_user.is_authenticated and current_user.get_user_club(club_id):
            return f(*args, **kwargs)

        # Unified guest check: any visitor (authenticated non-member or
        # anonymous) without a UserClub row for club_id is a guest of that
        # club. Both User and AnonymousUser now route through
        # has_club_permission, which consults the Guest role's per-club
        # matrix for non-members.
        if current_user.has_club_permission(Permissions.MEETING_VIEW_PUBLISHED, club_id):
            return f(*args, **kwargs)

        # No view permission for this club. Anonymous visitors with no Guest
        # permission for this club are bounced to login.
        if not current_user.is_authenticated:
            return redirect(url_for('auth_bp.login'))
        abort(403)
    return decorated_function


def is_module_enabled(module_name, club_id=None):
    """
    Check if a functional module is enabled for the specified club.
    
    Args:
        module_name (str): Name of the module
        club_id (int): Club ID. If None, uses current club context.
        
    Returns:
        bool: True if enabled, False otherwise.
    """
    if module_name == 'Core':
        return True
        
    if club_id is None:
        club_id = get_current_club_id()
        
    if not club_id:
        return True # Default to True if no club context is set yet
        
    # Check cache in request context `g`
    if not hasattr(g, 'module_states'):
        g.module_states = {}
        
    if (club_id, module_name) not in g.module_states:
        from app.models.club_module import ClubModule
        mod = ClubModule.query.filter_by(club_id=club_id, module_name=module_name).first()
        g.module_states[(club_id, module_name)] = mod.is_enabled if mod else True
        
    return g.module_states[(club_id, module_name)]

