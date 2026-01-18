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


def get_or_set_default_club():
    """
    Get current club ID or set to default if not set.
    
    Returns:
        int: Current club ID
    """
    from app.models import Club
    
    club_id = get_current_club_id()
    
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
    3. For anonymous users: Allows access if they have ABOUT_CLUB_VIEW permission.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask_login import current_user
        from flask import abort
        from app.auth.permissions import Permissions
        from app.models import ContactClub, Club, ExComm
        from app.models.base import db
        
        # Ensure club context is established
        club_id = get_or_set_default_club()
        if not club_id:
            abort(404, description="No club context found")
            
        if current_user.is_authenticated:
            from app.models import AuthRole, UserClub
            from app.auth.permissions import Permissions
            
            # SysAdmin can access any club - check if user has SysAdmin role in ANY club
            sys_role = AuthRole.get_by_name(Permissions.SYSADMIN)
            if sys_role:
                is_sysadmin = UserClub.query.filter_by(
                    user_id=current_user.id,
                    club_role_id=sys_role.id
                ).first()
                if is_sysadmin:
                    return f(*args, **kwargs)
            
            # Check if user has a UserClub record for THIS specific club
            user_club = UserClub.query.filter_by(user_id=current_user.id, club_id=club_id).first()
            
            if user_club and user_club.club_role_id:
                # User has a club membership with a role for this club
                role = db.session.get(AuthRole, user_club.club_role_id)
                
                # ClubAdmin and other roles can access their clubs
                # ClubAdmin and other roles can access their clubs
                if role:
                    return f(*args, **kwargs)
            
            # If we fall through here, the authenticated user is unauthorized for this club
            abort(403)
            
        else:
            # Anonymous guests: check if they have general club view permission
            # (The 'Guest' role in DB should typically have this)
            if hasattr(current_user, 'can') and not current_user.can(Permissions.ABOUT_CLUB_VIEW):
                from flask import redirect, url_for
                return redirect(url_for('auth_bp.login'))
            elif not hasattr(current_user, 'can'):
                # Fallback if 'can' method missing (shouldn't happen with correct AnonymousUser)
                 from flask import redirect, url_for
                 return redirect(url_for('auth_bp.login'))
                
        return f(*args, **kwargs)
    return decorated_function
