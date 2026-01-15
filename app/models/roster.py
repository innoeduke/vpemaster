"""Roster, role, and waitlist models."""
from sqlalchemy import func
from .base import db


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    icon = db.Column(db.String(50))
    type = db.Column(db.String(20), nullable=False)
    award_category = db.Column(db.String(30))
    needs_approval = db.Column(db.Boolean, nullable=False)
    is_distinct = db.Column(db.Boolean, nullable=False)
    is_member_only = db.Column(db.Boolean, default=False)


class RosterRole(db.Model):
    """Junction table for many-to-many relationship between Roster and Role"""
    __tablename__ = 'roster_roles'
    id = db.Column(db.Integer, primary_key=True)
    roster_id = db.Column(db.Integer, db.ForeignKey('roster.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    
    # Unique constraint to prevent duplicate role assignments
    __table_args__ = (
        db.UniqueConstraint('roster_id', 'role_id', name='uq_roster_role'),
    )


class Roster(db.Model):
    __tablename__ = 'roster'
    id = db.Column(db.Integer, primary_key=True)
    meeting_number = db.Column(db.Integer, nullable=False)
    order_number = db.Column(db.Integer, nullable=True)
    ticket = db.Column(db.String(20), nullable=True)
    contact_id = db.Column(db.Integer, db.ForeignKey(
        'Contacts.id'), nullable=True)
    contact_type = db.Column(db.String(50), nullable=True)

    contact = db.relationship('Contact', backref='roster_entries')
    roles = db.relationship('Role', secondary='roster_roles', backref='roster_entries')

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
    def delete_for_meeting(cls, meeting_number):
        """Deletes all roster entries and associated roles for a meeting."""
        rosters = cls.query.filter_by(meeting_number=meeting_number).all()
        roster_ids = [r.id for r in rosters]
        
        if roster_ids:
            # Delete assignments first
            RosterRole.query.filter(RosterRole.roster_id.in_(roster_ids)).delete(synchronize_session=False)
            # Delete roster entries
            cls.query.filter(cls.id.in_(roster_ids)).delete(synchronize_session=False)

    @staticmethod
    def sync_role_assignment(meeting_number, contact_id, role_obj, action):
        """
        Sync roster role assignments when booking/agenda changes.
        
        Args:
            meeting_number: Meeting number
            contact_id: Contact ID (or None for unassignment)
            role_obj: Role object being assigned/unassigned
            action: 'assign' or 'unassign'
        """
        if not contact_id or not role_obj:
            return
        
        # Find roster entry for this contact in this meeting
        roster_entry = Roster.query.filter_by(
            meeting_number=meeting_number,
            contact_id=contact_id
        ).first()
        
        if not roster_entry:
            if action == 'assign':
                # Fetch contact details
                from .contact import Contact
                contact = db.session.get(Contact, contact_id)
                contact_type = contact.Type
                is_officer = (contact.user and contact.user.is_officer) or contact.Type == 'Officer'

                # Logic for Order Number
                new_order = None
                if is_officer:
                    # Officers get the next available order number starting from 1000
                    max_order = db.session.query(func.max(Roster.order_number)).filter(
                        Roster.meeting_number == meeting_number,
                        Roster.order_number >= 1000
                    ).scalar()
                    new_order = (max_order or 999) + 1
                else:
                    # Members/Guests get blank order number (None)
                    new_order = None

                # Logic for Ticket Class
                ticket_class = "Role Taker" # Default for Guest
                if is_officer:
                    ticket_class = "Officer"
                elif contact_type == 'Member':
                    ticket_class = "Member"

                roster_entry = Roster(
                    meeting_number=meeting_number,
                    contact_id=contact_id,
                    order_number=new_order,
                    ticket=ticket_class,
                    contact_type=contact_type
                )
                db.session.add(roster_entry)
            else:
                # Contact not in roster and we are unassigning - nothing to do
                return
        
        if action == 'assign':
            # Add role if not already assigned
            roster_entry.add_role(role_obj)
        elif action == 'unassign':
            # Remove role if assigned
            roster_entry.remove_role(role_obj)


class Waitlist(db.Model):
    __tablename__ = 'waitlists'
    id = db.Column(db.Integer, primary_key=True)
    session_log_id = db.Column(db.Integer, db.ForeignKey(
        'Session_Logs.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey(
        'Contacts.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=True)

    session_log = db.relationship('SessionLog', backref='waitlists')
    contact = db.relationship('Contact', backref='waitlists')

    @classmethod
    def delete_for_meeting(cls, meeting_number):
        """Deletes all waitlist entries associated with a meeting."""
        from .session import SessionLog
        
        # Find session logs for the meeting to identify relevant waitlists
        session_logs = SessionLog.query.filter_by(Meeting_Number=meeting_number).all()
        session_log_ids = [log.id for log in session_logs]
        
        if session_log_ids:
            cls.query.filter(cls.session_log_id.in_(session_log_ids)).delete(synchronize_session=False)
