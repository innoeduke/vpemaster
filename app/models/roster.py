"""Roster, role, and waitlist models."""
from sqlalchemy import func
from .base import db



class MeetingRole(db.Model):
    __tablename__ = 'meeting_roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    icon = db.Column(db.String(50))
    type = db.Column(db.String(20), nullable=False)
    award_category = db.Column(db.String(30))
    needs_approval = db.Column(db.Boolean, nullable=False)
    has_single_owner = db.Column(db.Boolean, nullable=False)
    is_member_only = db.Column(db.Boolean, default=False)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=True, index=True)

    club = db.relationship('Club', backref='meeting_roles')

    __table_args__ = (
        db.UniqueConstraint('name', 'club_id', name='uq_meeting_role_name_club'),
    )

    @classmethod
    def get_all_for_club(cls, club_id):
        """
        Fetch all meeting roles for a club, merging Global and Local items.
        Local items override Global items with the same name.
        Returns a list of MeetingRole objects.
        """
        from ..constants import GLOBAL_CLUB_ID
        
        # Fetch Global items
        global_roles = cls.query.filter_by(club_id=GLOBAL_CLUB_ID).all()
        
        # Fetch Local items
        local_roles = []
        if club_id and club_id != GLOBAL_CLUB_ID:
            local_roles = cls.query.filter_by(club_id=club_id).all()
            
        # Merge: Local overwrites Global by name
        merged = {r.name: r for r in global_roles}
        for r in local_roles:
            merged[r.name] = r
            
        return sorted(list(merged.values()), key=lambda x: x.name)


class RosterRole(db.Model):
    """Junction table for many-to-many relationship between Roster and Role"""
    __tablename__ = 'roster_roles'
    id = db.Column(db.Integer, primary_key=True)
    roster_id = db.Column(db.Integer, db.ForeignKey('roster.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('meeting_roles.id'), nullable=False)
    
    # Unique constraint to prevent duplicate role assignments
    __table_args__ = (
        db.UniqueConstraint('roster_id', 'role_id', name='uq_roster_role'),
    )


class Roster(db.Model):
    __tablename__ = 'roster'
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('Meetings.id'), nullable=True, index=True)
    meeting = db.relationship('Meeting', foreign_keys=[meeting_id])
    @property
    def meeting_number(self):
        if self.meeting:
            return self.meeting.Meeting_Number
        return None
        
    @meeting_number.setter
    def meeting_number(self, value):
        """Setter for meeting_number for backward compatibility in tests."""
        from .meeting import Meeting
        if not self.meeting:
            m = Meeting.query.filter_by(Meeting_Number=value).first()
            if m:
                self.meeting = m
                self.meeting_id = m.id
        
    order_number = db.Column(db.Integer, nullable=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=True)
    
    ticket = db.relationship('Ticket')
    contact_id = db.Column(db.Integer, db.ForeignKey(
        'Contacts.id'), nullable=True)
    contact_type = db.Column(db.String(50), nullable=True)

    contact = db.relationship('Contact', back_populates='roster_entries')
    roles = db.relationship('app.models.roster.MeetingRole', secondary='roster_roles', backref='roster_entries')

    def add_role(self, role):
        """Add a role to this roster entry if not already assigned"""
        if not self.has_role(role):
            self.roles.append(role)
            return True
        return False

    def remove_role(self, role):
        """Remove a role from this roster entry if assigned"""
        if self.has_role(role):
            self.roles.remove(role)
            return True
        return False

    def has_role(self, role):
        """Check if this roster entry has the specified role"""
        return role in self.roles

    def clear_roles(self):
        """Remove all roles from this roster entry"""
        self.roles = []

    def get_role_names(self):
        """Get list of role names for this roster entry"""
        return [role.name for role in self.roles]

    @classmethod
    def delete_for_meeting(cls, meeting_id):
        """Deletes all roster entries and associated roles for a meeting."""
        rosters = cls.query.filter_by(meeting_id=meeting_id).all()
        roster_ids = [r.id for r in rosters]
        
        if roster_ids:
            # Delete assignments first
            RosterRole.query.filter(RosterRole.roster_id.in_(roster_ids)).delete(synchronize_session=False)
            # Delete roster entries
            cls.query.filter(cls.id.in_(roster_ids)).delete(synchronize_session=False)

    @staticmethod
    def sync_role_assignment(meeting_id, contact_id, role_obj, action):
        """
        Sync roster role assignments when booking/agenda changes.
        """
        if not contact_id or not role_obj:
            return
        
        # Find roster entry for this contact in this meeting
        roster_entry = Roster.query.filter_by(
            meeting_id=meeting_id,
            contact_id=contact_id
        ).first()
        
        # Fetch contact details for field syncing
        from .contact import Contact
        contact = db.session.get(Contact, contact_id)
        if not contact:
            return

        from ..auth.permissions import Permissions
        from .ticket import Ticket
        is_officer = (contact.user and contact.user.has_role(Permissions.STAFF)) or contact.Type == 'Officer'

        if not roster_entry:
            if action == 'assign':
                # Logic for Order Number
                new_order = None
                if is_officer:
                    # Officers get the next available order number starting from 1000
                    base_filter = Roster.meeting_id == meeting_id
                    max_order = db.session.query(func.max(Roster.order_number)).filter(
                        base_filter,
                        Roster.order_number >= 1000
                    ).scalar()
                    new_order = (max_order or 999) + 1
                else:
                    new_order = None

                # Logic for Ticket Class
                ticket_name = "Role-taker" # Default
                if is_officer:
                    ticket_name = "Officer"
                elif contact.Type == 'Member':
                    ticket_name = "Early-bird (Member)"

                ticket_obj = Ticket.query.filter_by(name=ticket_name).first()
                # Fallback to Role-taker if not found, though DB should have it
                if not ticket_obj:
                    ticket_obj = Ticket.query.filter_by(name="Role-taker").first()

                roster_entry = Roster(
                    meeting_id=meeting_id,
                    contact_id=contact_id,
                    order_number=new_order,
                    ticket_id=ticket_obj.id if ticket_obj else None,
                    contact_type='Officer' if is_officer else contact.Type
                )
                db.session.add(roster_entry)
            else:
                return
        else:
            # Update fields except order_number and ticket (per user request)
            roster_entry.contact_type = 'Officer' if is_officer else contact.Type
        
        if action == 'assign':
            # Add role if not already assigned
            roster_entry.add_role(role_obj)
        elif action == 'unassign':
            # Remove role ONLY if they have no other sessions with this role in this meeting
            from .session import SessionLog, SessionType, OwnerMeetingRoles
            from .meeting import Meeting
            remaining_role_session = db.session.query(SessionLog.id)\
                .join(SessionType, SessionLog.Type_ID == SessionType.id)\
                .join(Meeting, SessionLog.meeting_id == Meeting.id)\
                .join(MeetingRole, SessionType.role_id == MeetingRole.id)\
                .filter(SessionLog.meeting_id == meeting_id)\
                .filter(db.exists().where(
                    db.and_(
                        OwnerMeetingRoles.contact_id == contact_id,
                        OwnerMeetingRoles.meeting_id == Meeting.id,
                        OwnerMeetingRoles.role_id == MeetingRole.id,
                        db.or_(
                            OwnerMeetingRoles.session_log_id == SessionLog.id,
                            OwnerMeetingRoles.session_log_id.is_(None)
                        )
                    )
                ))\
                .filter(SessionType.role_id == role_obj.id)\
                .first()
            
            if not remaining_role_session:
                roster_entry.remove_role(role_obj)
            
            # Delete roster entry if no roles left (and not an officer/cancelled)
            # Delete roster entry if no roles left (and not an officer/cancelled)
            if not roster_entry.roles:
                # Access ticket name via relationship
                t_name = roster_entry.ticket.name if roster_entry.ticket else None
                if t_name not in ['Officer', 'Cancelled'] and not is_officer:
                    db.session.delete(roster_entry)


class Waitlist(db.Model):
    __tablename__ = 'waitlists'
    id = db.Column(db.Integer, primary_key=True)
    session_log_id = db.Column(db.Integer, db.ForeignKey(
        'Session_Logs.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey(
        'Contacts.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=True)

    session_log = db.relationship('SessionLog', backref='waitlists')
    contact = db.relationship('Contact', back_populates='waitlists')

    @classmethod
    def delete_for_meeting(cls, meeting_id):
        """Deletes all waitlist entries associated with a meeting."""
        from .session import SessionLog
        from app.auth.permissions import Permissions
        from app.models.meeting import Meeting
        
        # Find session logs for the meeting to identify relevant waitlists
        session_logs = SessionLog.query.filter_by(meeting_id=meeting_id).all()
        session_log_ids = [log.id for log in session_logs]
        
        if session_log_ids:
            cls.query.filter(cls.session_log_id.in_(session_log_ids)).delete(synchronize_session=False)
