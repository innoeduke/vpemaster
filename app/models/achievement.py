"""Achievement model for tracking member achievements."""
from .base import db


class Achievement(db.Model):
    __tablename__ = 'achievements'
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'), nullable=False)
    member_id = db.Column(db.String(50))  # Redundant but requested
    issue_date = db.Column(db.Date, nullable=False)
    achievement_type = db.Column(db.Enum('level-completion', 'path-completion', 'program-completion', 
                                         name='achievement_type_enum'), nullable=False)
    path_name = db.Column(db.String(100))
    level = db.Column(db.Integer)
    notes = db.Column(db.Text)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=True, index=True)

    contact = db.relationship('Contact', back_populates='achievements')
    club = db.relationship('Club')
