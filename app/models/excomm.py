"""ExComm (Executive Committee) model for tracking officer terms."""
from datetime import datetime
from .base import db


class ExComm(db.Model):
    __tablename__ = 'excomm'
    
    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=False)
    excomm_term = db.Column(db.String(20), nullable=False, index=True)  # e.g., "26H1", "26H2"
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    excomm_name = db.Column(db.String(100), nullable=True)  # e.g., "Memory Makers"
    
    # Officer positions - all nullable to allow flexibility
    president_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'), nullable=True)
    vpe_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'), nullable=True)
    vpm_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'), nullable=True)
    vppr_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'), nullable=True)
    secretary_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'), nullable=True)
    treasurer_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'), nullable=True)
    saa_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'), nullable=True)
    ipp_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships to Contact model for each officer position
    president = db.relationship('Contact', foreign_keys=[president_id], backref='excomm_as_president')
    vpe = db.relationship('Contact', foreign_keys=[vpe_id], backref='excomm_as_vpe')
    vpm = db.relationship('Contact', foreign_keys=[vpm_id], backref='excomm_as_vpm')
    vppr = db.relationship('Contact', foreign_keys=[vppr_id], backref='excomm_as_vppr')
    secretary = db.relationship('Contact', foreign_keys=[secretary_id], backref='excomm_as_secretary')
    treasurer = db.relationship('Contact', foreign_keys=[treasurer_id], backref='excomm_as_treasurer')
    saa = db.relationship('Contact', foreign_keys=[saa_id], backref='excomm_as_saa')
    ipp = db.relationship('Contact', foreign_keys=[ipp_id], backref='excomm_as_ipp')
    
    def __repr__(self):
        return f'<ExComm {self.excomm_term}: {self.excomm_name}>'
    
    def get_officers(self):
        """
        Returns dictionary of all officer positions and their Contact objects.
        
        Returns:
            dict: {role_name: Contact object or None}
        """
        return {
            'President': self.president,
            'VPE': self.vpe,
            'VPM': self.vpm,
            'VPPR': self.vppr,
            'Secretary': self.secretary,
            'Treasurer': self.treasurer,
            'SAA': self.saa,
            'IPP': self.ipp
        }
    
    def get_officer_by_role(self, role_name):
        """
        Returns Contact for a specific officer role.
        
        Args:
            role_name (str): Role name (case-insensitive)
            
        Returns:
            Contact or None: Contact object for the officer, or None if not found
        """
        role_map = {
            'president': self.president,
            'vpe': self.vpe,
            'vpm': self.vpm,
            'vppr': self.vppr,
            'secretary': self.secretary,
            'treasurer': self.treasurer,
            'saa': self.saa,
            'ipp': self.ipp
        }
        return role_map.get(role_name.lower())
    
    def to_dict(self):
        """Convert excomm to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'club_id': self.club_id,
            'excomm_term': self.excomm_term,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'excomm_name': self.excomm_name,
            'officers': {
                'president': {'id': self.president_id, 'name': self.president.Name if self.president else None},
                'vpe': {'id': self.vpe_id, 'name': self.vpe.Name if self.vpe else None},
                'vpm': {'id': self.vpm_id, 'name': self.vpm.Name if self.vpm else None},
                'vppr': {'id': self.vppr_id, 'name': self.vppr.Name if self.vppr else None},
                'secretary': {'id': self.secretary_id, 'name': self.secretary.Name if self.secretary else None},
                'treasurer': {'id': self.treasurer_id, 'name': self.treasurer.Name if self.treasurer else None},
                'saa': {'id': self.saa_id, 'name': self.saa.Name if self.saa else None},
                'ipp': {'id': self.ipp_id, 'name': self.ipp.Name if self.ipp else None}
            },
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
