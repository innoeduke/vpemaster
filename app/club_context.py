"""Club context utilities for multi-club support."""
from flask import session, g
from functools import wraps


def get_current_club_id():
    """
    Get the current club ID from session.
    
    Returns:
        int: Current club ID or None if not set
    """
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
        # Try to get user's primary club
        from flask_login import current_user
        if current_user.is_authenticated and hasattr(current_user, 'contact'):
            primary_club = current_user.contact.get_primary_club()
            if primary_club:
                set_current_club_id(primary_club.id)
                return primary_club.id
        
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
    if not user or not hasattr(user, 'contact'):
        return []
    
    return user.contact.get_clubs()


def switch_club(club_id):
    """
    Switch to a different club context.
    
    Args:
        club_id (int): ID of club to switch to
        
    Returns:
        bool: True if successful, False otherwise
    """
    from app.models import Club
    
    club = Club.query.get(club_id)
    if club:
        set_current_club_id(club_id)
        return True
    return False
