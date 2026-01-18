"""ContactClub junction table for many-to-many relationship between contacts and clubs."""
from datetime import datetime, timezone
from .base import db


class ContactClub(db.Model):
    """
    Junction table linking contacts to clubs with membership details.
    
    NOTE: Both user_clubs and contact_clubs include contact_id and club_id for 
    associating contacts with clubs. The difference is that 'contact_clubs' contains 
    BOTH user contacts and guest contacts.
    """
    __tablename__ = 'contact_clubs'
    
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('Contacts.id', ondelete='CASCADE'), nullable=False)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    contact = db.relationship('Contact', back_populates='club_memberships')
    club = db.relationship('Club', backref=db.backref('contact_memberships', cascade='all, delete-orphan'))
    
    # Constraints and indexes
    __table_args__ = (
        db.UniqueConstraint('contact_id', 'club_id', name='uq_contact_club'),
        db.Index('ix_contact_clubs_contact', 'contact_id'),
        db.Index('ix_contact_clubs_club', 'club_id'),
    )
    
    def __repr__(self):
        return f'<ContactClub contact_id={self.contact_id} club_id={self.club_id}>'
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'club_id': self.club_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
