from datetime import date
from .base import db

class ContactPath(db.Model):
    """
    Tracks pathways registered for a contact, including their status (working/completed)
    and which pathway is currently marked as default/active.
    """
    __tablename__ = 'contact_paths'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('Contacts.id', ondelete='CASCADE'), nullable=False)
    path_id = db.Column(db.Integer, db.ForeignKey('pathways.id', ondelete='CASCADE'), nullable=False)
    status = db.Column(db.String(20), default='working', nullable=False)  # 'working', 'completed'
    is_default = db.Column(db.Boolean, default=False, nullable=False, server_default=db.text('0'))
    registered_date = db.Column(db.Date, default=date.today, nullable=True)
    completed_date = db.Column(db.Date, nullable=True)

    # Relationships
    contact = db.relationship('Contact', back_populates='registered_paths')
    pathway = db.relationship('Pathway')

    # Constraints and indexes
    __table_args__ = (
        db.UniqueConstraint('contact_id', 'path_id', name='uq_contact_path'),
        db.Index('ix_contact_paths_contact', 'contact_id'),
        db.Index('ix_contact_paths_pathway', 'path_id'),
    )

    def __repr__(self):
        return f'<ContactPath contact_id={self.contact_id} path_id={self.path_id} status={self.status} is_default={self.is_default}>'

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'contact_id': self.contact_id,
            'path_id': self.path_id,
            'pathway_name': self.pathway.name if self.pathway else None,
            'pathway_abbr': self.pathway.abbr if self.pathway else None,
            'status': self.status,
            'is_default': self.is_default,
            'registered_date': self.registered_date.isoformat() if self.registered_date else None,
            'completed_date': self.completed_date.isoformat() if self.completed_date else None
        }
