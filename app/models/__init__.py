"""
Models package for VPEMaster application.

This package organizes models into logical modules while maintaining
backward compatibility with existing imports.
"""
from .base import db

# Import all models from their respective modules
from .contact import Contact
from .user import User, AnonymousUser

from .project import Project, Pathway, PathwayProject, LevelRole
from .meeting import Meeting
from .session import SessionType, SessionLog, OwnerMeetingRoles
from .roster import Roster, RosterRole, MeetingRole, Waitlist
from .voting import Vote
from .media import Media
from .achievement import Achievement
from .message import Message
from .ticket import Ticket
from .planner import Planner
from .program import Program, ProgramTask, ProgramEnrollment

from .upload_link import UploadLink
from .chat_message import ChatMessage
from .issue import Issue, IssueComment

# Import permission system models
from .permission import Permission
from .role import Role as AuthRole
from .role_permission import RolePermission

from .permission_audit import PermissionAudit

# Import club and excomm models
from .club import Club
from .club_module import ClubModule
from .club_rule import ClubRule
from .contact_club import ContactClub
from .excomm import ExComm
from .excomm_officer import ExcommOfficer
from .user_club import UserClub

# Import Flask-Login user loader
from .. import login_manager

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

login_manager.anonymous_user = AnonymousUser

from .contact_path import ContactPath

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
    'MeetingRole',
    'Waitlist',
    'Vote',
    'Media',
    'Achievement',
    'Message',
    'load_user',
    # Permission system models
    'Permission',
    'AuthRole',
    'RolePermission',

    'PermissionAudit',
    # Club and ExComm models
    'Club',
    'ClubModule',
    'ClubRule',
    'ContactClub',
    'ContactPath',
    'ExComm',
    'ExcommOfficer',
    'UserClub',
    'OwnerMeetingRoles',
    'Planner',
    'Program',
    'ProgramTask',
    'ProgramEnrollment',

    'UploadLink',
    'ChatMessage',
    'Issue',
    'IssueComment',
]
