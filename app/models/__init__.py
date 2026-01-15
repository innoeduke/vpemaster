"""
Models package for VPEMaster application.

This package organizes models into logical modules while maintaining
backward compatibility with existing imports.
"""
from .base import db

# Import all models from their respective modules
from .contact import Contact
from .user import User
from .project import Project, Pathway, PathwayProject, LevelRole
from .meeting import Meeting
from .session import SessionType, SessionLog
from .roster import Roster, RosterRole, Role, Waitlist
from .voting import Vote
from .media import Media
from .achievement import Achievement

# Import permission system models
from .permission import Permission
from .role import Role as AuthRole  # Alias to avoid conflict with roster.Role
from .role_permission import RolePermission
from .user_role import UserRole as UserRoleAssociation

# Import Flask-Login user loader
from .. import login_manager

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# Export all models for backward compatibility
__all__ = [
    'db',
    'Contact',
    'User',
    'Project',
    'Pathway',
    'PathwayProject',
    'LevelRole',
    'Meeting',
    'SessionType',
    'SessionLog',
    'Roster',
    'RosterRole',
    'Role',
    'Waitlist',
    'Vote',
    'Media',
    'Achievement',
    'load_user',
    # Permission system models
    'Permission',
    'AuthRole',
    'RolePermission',
    'UserRoleAssociation',
]
