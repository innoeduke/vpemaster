"""Voting model for best awards."""
from .base import db


class Vote(db.Model):
    __tablename__ = 'votes'
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('Meetings.id'), nullable=True, index=True)
    meeting = db.relationship('Meeting', backref=db.backref('votes', cascade='all, delete-orphan'))

    @property
    def meeting_number(self):
        if self.meeting:
            return self.meeting.Meeting_Number
        return None

    @meeting_number.setter
    def meeting_number(self, value):
        """Setter for meeting_number for backward compatibility in tests."""
        from .meeting import Meeting
        if not self.meeting:
            m = Meeting.query.filter_by(Meeting_Number=value).first()
            if m:
                self.meeting = m
                self.meeting_id = m.id
    voter_identifier = db.Column(db.String(64), nullable=False)
    award_category = db.Column(db.String(50), nullable=True)
    contact_id = db.Column(db.Integer, db.ForeignKey(
        'Contacts.id'), nullable=True)
    question = db.Column(db.String(255), nullable=True)
    score = db.Column(db.Integer, nullable=True)
    comments = db.Column(db.Text, nullable=True)

    # Relationship with Contact table
    contact = db.relationship('Contact', backref='votes')

    # Add index for performance
    __table_args__ = (
        db.Index('idx_meeting_voter', 'meeting_id', 'voter_identifier'),
    )

    @classmethod
    def delete_for_meeting(cls, meeting_id):
        """Deletes all votes for a meeting."""
        cls.query.filter_by(meeting_id=meeting_id).delete(synchronize_session=False)

class Award(db.Model):
    __tablename__ = 'awards'
    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    max_votes_per_user = db.Column(db.Integer, default=1, nullable=False)
    max_winners = db.Column(db.Integer, default=1, nullable=False)

    club = db.relationship('Club', backref=db.backref('awards_rel', cascade='all, delete-orphan'))

    __table_args__ = (
        db.UniqueConstraint('club_id', 'category', name='uq_club_award_category'),
    )


class AwardRole(db.Model):
    __tablename__ = 'award_roles'
    id = db.Column(db.Integer, primary_key=True)
    award_id = db.Column(db.Integer, db.ForeignKey('awards.id', ondelete='CASCADE'), nullable=False, index=True)
    meeting_role_id = db.Column(db.Integer, db.ForeignKey('meeting_roles.id', ondelete='CASCADE'), nullable=False, index=True)

    award = db.relationship('Award', backref=db.backref('role_associations', cascade='all, delete-orphan'))
    meeting_role = db.relationship('MeetingRole')

    __table_args__ = (
        db.UniqueConstraint('award_id', 'meeting_role_id', name='uq_award_role'),
    )


class MeetingAwardConfig(db.Model):
    __tablename__ = 'meeting_award_configs'
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('Meetings.id', ondelete='CASCADE'), nullable=False, index=True)
    award_category = db.Column(db.String(50), nullable=False)
    award_id = db.Column(db.Integer, db.ForeignKey('awards.id', ondelete='SET NULL'), nullable=True, index=True)
    max_votes_per_user = db.Column(db.Integer, default=1, nullable=False)
    max_winners = db.Column(db.Integer, default=1, nullable=False)
    associated_role = db.Column(db.String(50), nullable=True)

    meeting = db.relationship('Meeting', backref=db.backref('award_configs', cascade='all, delete-orphan'))
    award = db.relationship('Award')

    __table_args__ = (
        db.UniqueConstraint('meeting_id', 'award_category', name='uq_meeting_award_config'),
    )


class AwardRoleConfig(db.Model):
    __tablename__ = 'award_role_configs'
    id = db.Column(db.Integer, primary_key=True)
    award_config_id = db.Column(
        db.Integer,
        db.ForeignKey('meeting_award_configs.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )
    meeting_role_id = db.Column(
        db.Integer,
        db.ForeignKey('meeting_roles.id', ondelete='CASCADE'),
        nullable=False, index=True,
    )

    award_config = db.relationship(
        'MeetingAwardConfig',
        backref=db.backref('role_associations', cascade='all, delete-orphan'),
    )
    meeting_role = db.relationship('MeetingRole')

    __table_args__ = (
        db.UniqueConstraint('award_config_id', 'meeting_role_id', name='uq_award_role_config'),
    )


class MeetingAwardWinner(db.Model):
    __tablename__ = 'meeting_award_winners'
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('Meetings.id', ondelete='CASCADE'), nullable=False, index=True)
    award_category = db.Column(db.String(50), nullable=False)
    award_id = db.Column(db.Integer, db.ForeignKey('awards.id', ondelete='SET NULL'), nullable=True, index=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('Contacts.id', ondelete='CASCADE'), nullable=False, index=True)

    meeting = db.relationship('Meeting', backref=db.backref('award_winners', cascade='all, delete-orphan'))
    award = db.relationship('Award')
    contact = db.relationship('Contact')

    __table_args__ = (
        db.UniqueConstraint('meeting_id', 'award_category', 'contact_id', name='uq_meeting_award_winner'),
    )
