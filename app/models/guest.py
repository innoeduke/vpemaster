"""Guest model for tracking club guests and visitors."""
from datetime import datetime, timezone
from .base import db


class Guest(db.Model):
    __tablename__ = 'guests'
    
    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(50), nullable=True)  # e.g., 'Visited', 'Joined', 'Pending'
    type = db.Column(db.String(50), nullable=True)  # e.g., 'Guest', 'Prospective Member'
    created_date = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    
    # Relationship
    club = db.relationship('Club', backref=db.backref('guests', lazy='dynamic'))
    
    def __repr__(self):
        return f'<Guest {self.name} - Club {self.club_id}>'
    
    def to_dict(self):
        """Convert guest to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'club_id': self.club_id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'status': self.status,
            'type': self.type,
            'created_date': self.created_date.isoformat() if self.created_date else None,
            'notes': self.notes
        }
