"""UploadLink model for file upload feature."""
from datetime import datetime
from .base import db

class UploadLink(db.Model):
    __tablename__ = 'upload_links'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id', ondelete='CASCADE'), nullable=True, index=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('Meetings.id', ondelete='SET NULL'), nullable=True, index=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Optional constraints
    max_files = db.Column(db.Integer, nullable=True)
    max_file_size = db.Column(db.Integer, nullable=True) # in MB
    
    # Relationships
    club = db.relationship('Club', backref='upload_links')
    meeting = db.relationship('Meeting', backref='upload_links')
    creator = db.relationship('User', backref='created_upload_links')
    
    def __repr__(self):
        return f'<UploadLink {self.code} title={self.title}>'
        
    @property
    def is_expired(self):
        if self.expires_at:
            return datetime.now() > self.expires_at
        return False
