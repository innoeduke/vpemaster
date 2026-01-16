"""ContactClub junction table for many-to-many relationship between contacts and clubs."""
from datetime import datetime
from .base import db


class ContactClub(db.Model):
    """Junction table linking contacts to clubs with membership details."""
    __tablename__ = 'contact_clubs'
    
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('Contacts.id', ondelete='CASCADE'), nullable=False)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id', ondelete='CASCADE'), nullable=False)
    membership_type = db.Column(db.String(50), nullable=True)  # 'Member', 'Guest', 'Officer'
    joined_date = db.Column(db.Date, nullable=True)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    contact = db.relationship('Contact', backref='club_memberships')
    club = db.relationship('Club', backref='contact_memberships')
    
    # Constraints and indexes
    __table_args__ = (
        db.UniqueConstraint('contact_id', 'club_id', name='uq_contact_club'),
        db.Index('ix_contact_clubs_contact', 'contact_id'),
        db.Index('ix_contact_clubs_club', 'club_id'),
    )
    
    def __repr__(self):
        return f'<ContactClub contact_id={self.contact_id} club_id={self.club_id} type={self.membership_type}>'
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'club_id': self.club_id,
            'membership_type': self.membership_type,
            'joined_date': self.joined_date.isoformat() if self.joined_date else None,
            'is_primary': self.is_primary,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
