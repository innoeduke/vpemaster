"""Club model for multi-club support."""
from datetime import datetime, timezone
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
    logo_url = db.Column(db.String(255), nullable=True, default='images/club_logo.webp')
    founded_date = db.Column(db.Date, nullable=True)
    current_excomm_id = db.Column(db.Integer, db.ForeignKey('excomm.id', use_alter=True, name='fk_club_current_excomm'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
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
        order_by='ExComm.start_date.desc()',
        cascade='all, delete-orphan'
    )
    meetings = db.relationship(
        'Meeting',
        back_populates='club',
        cascade='all, delete-orphan'
    )
    
    @property
    def effective_logo_url(self):
        """Returns the logo URL if it exists, otherwise returns the default logo."""
        from flask import current_app
        import os
        
        default_logo = 'images/club_logo.webp'
        url = self.logo_url
        
        if not url:
            return default_logo
            
        # Strip potential legacy 'static/' prefix if present in DB
        if url.startswith('static/'):
            url = url[len('static/'):]
            
        # Check if file exists in static folder
        try:
            # current_app.static_folder is the absolute path to the static directory
            static_folder = current_app.static_folder
            file_path = os.path.join(static_folder, url)
            
            if os.path.exists(file_path) and os.path.isfile(file_path):
                return url
        except Exception:
            pass
            
        return default_logo

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
            'logo_url': self.logo_url,
            'founded_date': self.founded_date.isoformat() if self.founded_date else None,
            'current_excomm_id': self.current_excomm_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
