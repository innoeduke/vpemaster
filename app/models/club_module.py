"""ClubModule model to store toggle states for functional modules."""
from datetime import datetime, timezone
from .base import db


class ClubModule(db.Model):
    __tablename__ = 'club_modules'
    
    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id', ondelete='CASCADE'), nullable=False, index=True)
    module_name = db.Column(db.String(50), nullable=False)
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        db.UniqueConstraint('club_id', 'module_name', name='uq_club_module'),
    )
    
    # Relationship to Club
    club = db.relationship('Club', backref=db.backref('modules_rel', cascade='all, delete-orphan', lazy='dynamic'))

    @classmethod
    def initialize_club_modules(cls, club_id):
        """Initializes all switchable modules as disabled (False) for a newly created club."""
        switchable_modules = [
            "Booking", "Voting", "Roster", "Calendar", 
            "Chatbot", "Journal", "Club Directory", "Planner", "Lucky Draw", "Upload", "Data/Slides Export"
        ]
        for name in switchable_modules:
            mod = cls(club_id=club_id, module_name=name, is_enabled=False)
            db.session.add(mod)

    def __repr__(self):
        return f'<ClubModule {self.module_name} in Club {self.club_id}: {self.is_enabled}>'
