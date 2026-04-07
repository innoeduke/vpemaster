"""UserClub junction table for many-to-many relationship between users and clubs."""
from datetime import datetime, timezone
from .base import db


class UserClub(db.Model):
    """
    Junction table linking users to clubs with membership details.
    
    NOTE: Both user_clubs and contact_clubs include contact_id and club_id for 
    associating contacts with clubs. The difference is that 'user_clubs' contains 
    ONLY contacts linked to users.
    """
    __tablename__ = 'user_clubs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('Contacts.id', ondelete='CASCADE'), nullable=True)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id', ondelete='CASCADE'), nullable=False)
    auth_role_id = db.Column(db.Integer, db.ForeignKey('auth_roles.id'), nullable=True, index=True)
    current_path_id = db.Column(db.Integer, db.ForeignKey('pathways.id'), nullable=True)
    joined_date = db.Column(db.Date, nullable=True)
    is_home = db.Column(db.Boolean, default=False, nullable=False)  # Indicates if this is the user's home club
    mentor_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'), nullable=True)
    next_project_id = db.Column(db.Integer, db.ForeignKey('Projects.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = db.relationship('User', backref=db.backref('club_memberships', cascade='all, delete-orphan'))
    contact = db.relationship('Contact', foreign_keys=[contact_id], back_populates='user_club_records')
    club = db.relationship('Club', backref=db.backref('user_memberships', cascade='all, delete-orphan'))
    auth_role = db.relationship('Role', foreign_keys=[auth_role_id], lazy='joined')
    current_path = db.relationship('Pathway', foreign_keys=[current_path_id])
    mentor = db.relationship('Contact', foreign_keys=[mentor_id])
    next_project = db.relationship('Project', foreign_keys=[next_project_id])

    @property
    def club_role(self):
        """
        Backwards compatibility: Return the role object.
        Used by existing code that expects a single role.
        """
        return self.auth_role
    
    def __init__(self, **kwargs):
        super(UserClub, self).__init__(**kwargs)
        # contact_id should be explicitly provided or managed by User.ensure_contact

    # Constraints and indexes
    __table_args__ = (
        db.UniqueConstraint('user_id', 'club_id', name='uq_user_club'),
        db.Index('ix_user_clubs_user', 'user_id'),
        db.Index('ix_user_clubs_club', 'club_id'),
    )
    
    def __repr__(self):
        return f'<UserClub user_id={self.user_id} contact_id={self.contact_id} club_id={self.club_id} is_home={self.is_home}>'
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'contact_id': self.contact_id,
            'club_id': self.club_id,
            'auth_role_id': self.auth_role_id,
            'current_path_id': self.current_path_id,
            'joined_date': self.joined_date.isoformat() if self.joined_date else None,
            'is_home': self.is_home,
            'mentor_id': self.mentor_id,
            'next_project_id': self.next_project_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
