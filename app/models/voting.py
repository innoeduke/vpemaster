"""Voting model for best awards."""
from .base import db


class Vote(db.Model):
    __tablename__ = 'votes'
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('Meetings.id'), nullable=True, index=True)
    @property
    def meeting_number(self):
        if self.meeting:
            return self.meeting.Meeting_Number
        return None
    voter_identifier = db.Column(db.String(64), nullable=False)
    award_category = db.Column(db.Enum('speaker', 'evaluator', 'role-taker',
                               'table-topic', name='award_category_enum'), nullable=True)
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
