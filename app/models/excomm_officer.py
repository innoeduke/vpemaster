"""Excomm Officer association model."""
from .base import db

class ExcommOfficer(db.Model):
    __tablename__ = 'excomm_officers'
    
    id = db.Column(db.Integer, primary_key=True)
    excomm_id = db.Column(db.Integer, db.ForeignKey('excomm.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'), nullable=False)
    meeting_role_id = db.Column(db.Integer, db.ForeignKey('meeting_roles.id'), nullable=False)
    
    # Relationships
    excomm = db.relationship('ExComm', back_populates='officers')
    contact = db.relationship('Contact', backref='officer_roles')
    meeting_role = db.relationship('MeetingRole')
    
    __table_args__ = (
        db.UniqueConstraint('excomm_id', 'meeting_role_id', name='uq_excomm_role'),
    )

    def __repr__(self):
        return f'<ExcommOfficer {self.excomm_id} {self.meeting_role.name}: {self.contact.Name}>'
