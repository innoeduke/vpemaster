"""ClubRule model to store toggle states for booking rules."""
from datetime import datetime, timezone
from .base import db


class ClubRule(db.Model):
    __tablename__ = 'club_rules'

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id', ondelete='CASCADE'), nullable=False, index=True)
    rule_name = db.Column(db.String(50), nullable=False)
    is_enabled = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('club_id', 'rule_name', name='uq_club_rule'),
    )

    club = db.relationship('Club', backref=db.backref('rules_rel', cascade='all, delete-orphan', lazy='dynamic'))

    def __repr__(self):
        return f'<ClubRule {self.rule_name} in Club {self.club_id}: {self.is_enabled}>'
