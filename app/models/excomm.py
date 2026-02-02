"""ExComm (Executive Committee) model for tracking officer terms."""
from datetime import datetime, timezone
from .base import db


class ExComm(db.Model):
    __tablename__ = 'excomm'
    
    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id', use_alter=True, name='fk_excomm_club'), nullable=False)
    excomm_term = db.Column(db.String(20), nullable=False, index=True)  # e.g., "26H1", "26H2"
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    excomm_name = db.Column(db.String(100), nullable=True)  # e.g., "Memory Makers"
    
    # Officer positions are now handled via the excomm_officers association table
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    officers = db.relationship('ExcommOfficer', back_populates='excomm', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ExComm {self.excomm_term}: {self.excomm_name}>'
    
    def get_officers(self):
        """
        Returns dictionary of all officer positions and their Contact objects.
        
        Returns:
            dict: {role_name: Contact object or None}
        """
        officers = {}
        
        # Populate from association table
        for officer_link in self.officers:
            role_name = officer_link.meeting_role.name
            officers[role_name] = officer_link.contact
            
        return officers
    
    def get_officer_by_role(self, role_name):
        """
        Returns Contact for a specific officer role.
        
        Args:
            role_name (str): Role name (case-insensitive)
            
        Returns:
            Contact or None: Contact object for the officer, or None if not found
        """
        officers = self.get_officers()
        role_name_lower = role_name.lower()
        
        for r_name, contact in officers.items():
            if r_name.lower() == role_name_lower:
                return contact
        return None
    
    def to_dict(self):
        """Convert excomm to dictionary for JSON serialization."""
        officers_dict = {}
        officers = self.get_officers()
            
        for role_name, contact in officers.items():
            if contact:
                officers_dict[role_name.lower()] = {
                    'id': contact.id,
                    'name': contact.Name
                }

        return {
            'id': self.id,
            'club_id': self.club_id,
            'excomm_term': self.excomm_term,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'excomm_name': self.excomm_name,
            'officers': officers_dict,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
