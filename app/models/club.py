"""Club model for multi-club support."""
from datetime import datetime
from .base import db


class Club(db.Model):
    __tablename__ = 'clubs'
    
    id = db.Column(db.Integer, primary_key=True)
    club_no = db.Column(db.String(20), unique=True, nullable=False, index=True)
    club_name = db.Column(db.String(200), nullable=False)
    short_name = db.Column(db.String(100), nullable=True)
    district = db.Column(db.String(50), nullable=True)
    division = db.Column(db.String(50), nullable=True)
    area = db.Column(db.String(50), nullable=True)
    club_address = db.Column(db.Text, nullable=True)
    meeting_date = db.Column(db.String(100), nullable=True)  # e.g., "Every Wednesday"
    meeting_time = db.Column(db.Time, nullable=True)
    contact_phone_number = db.Column(db.String(50), nullable=True)
    website = db.Column(db.String(255), nullable=True)
    founded_date = db.Column(db.Date, nullable=True)
    current_excomm_id = db.Column(db.Integer, db.ForeignKey('excomm.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    current_excomm = db.relationship(
        'ExComm',
        foreign_keys=[current_excomm_id],
        backref=db.backref('current_for_club', uselist=False),
        post_update=True  # Allows circular reference
    )
    excomm_history = db.relationship(
        'ExComm',
        foreign_keys='ExComm.club_id',
        backref='club',
        lazy='dynamic',
        order_by='ExComm.start_date.desc()'
    )
    
    def __repr__(self):
        return f'<Club {self.club_no}: {self.club_name}>'
    
    def to_dict(self):
        """Convert club to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'club_no': self.club_no,
            'club_name': self.club_name,
            'short_name': self.short_name,
            'district': self.district,
            'division': self.division,
            'area': self.area,
            'club_address': self.club_address,
            'meeting_date': self.meeting_date,
            'meeting_time': self.meeting_time.strftime('%H:%M') if self.meeting_time else None,
            'contact_phone_number': self.contact_phone_number,
            'website': self.website,
            'founded_date': self.founded_date.isoformat() if self.founded_date else None,
            'current_excomm_id': self.current_excomm_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
