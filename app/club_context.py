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
            sys_role = AuthRole.get_by_name(Permissions.ADMIN)
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
                if role:
                    return f(*args, **kwargs)
            
            # Legacy/Fallback: Check if user is an officer in the current club's ExComm
            club = db.session.get(Club, club_id)
            if club and club.current_excomm_id:
                excomm = db.session.get(ExComm, club.current_excomm_id)
                if excomm and hasattr(current_user, 'Contact_ID') and current_user.Contact_ID:
                    contact_id = current_user.Contact_ID
                    officer_ids = [
                        excomm.president_id, excomm.vpe_id, excomm.vpm_id, excomm.vppr_id,
                        excomm.secretary_id, excomm.treasurer_id, excomm.saa_id, excomm.ipp_id
                    ]
                    if contact_id in officer_ids:
                        return f(*args, **kwargs)
            
            # Check for explicit membership if user is linked to a contact
            if hasattr(current_user, 'Contact_ID') and current_user.Contact_ID:
                membership = ContactClub.query.filter_by(
                    contact_id=current_user.Contact_ID,
                    club_id=club_id
                ).first()
                if not membership:
                    abort(403, description="You are not authorized for this club")
            else:
                # User has no contact linked - might be a legacy user or system user
                # Fallback to permission check
                if not current_user.can(Permissions.ABOUT_CLUB_VIEW):
                    abort(403)
        else:
            # Anonymous guests: check if they have general club view permission
            # (The 'Guest' role in DB should typically have this)
            if not current_user.can(Permissions.ABOUT_CLUB_VIEW):
                abort(403)
                
        return f(*args, **kwargs)
    return decorated_function
