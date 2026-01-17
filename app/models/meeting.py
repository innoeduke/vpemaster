"""Meeting model."""
from sqlalchemy.dialects import mysql
from .base import db


class Meeting(db.Model):
    __tablename__ = 'Meetings'
    
    # Meeting Type Mapping to Template Files
    TYPE_TO_TEMPLATE = {
        'Keynote Speech': 'default.csv',
        'Speech Marathon': 'speech_marathon.csv',
        'Speech Contest': 'speech_contest.csv',
        'Panel Discussion': 'panel_discussion.csv',
        'Debate': 'debate.csv',
        'Pecha Kucha': 'pecha_kucha.csv',
        'Gavel Passing': 'gavel_passing.csv',
        'Club Election': 'club_election.csv'
    }

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=False, index=True)
    type = db.Column(db.String(255), default='Keynote Speech')
    Meeting_Number = db.Column(mysql.SMALLINT(unsigned=True), unique=True, nullable=False)
    Meeting_Date = db.Column(db.Date)
    Meeting_Title = db.Column(db.String(255))
    Subtitle = db.Column(db.String(255), nullable=True)
    Start_Time = db.Column(db.Time)
    Meeting_Template = db.Column(db.String(100))
    WOD = db.Column(db.String(100))
    best_table_topic_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    best_evaluator_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    best_speaker_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    best_role_taker_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    media_id = db.Column(db.Integer, db.ForeignKey('Media.id', use_alter=True))
    ge_mode = db.Column(db.Integer, default=0)
    status = db.Column(db.Enum('unpublished', 'not started', 'running', 'finished', 'cancelled', name='meeting_status'),
                       default='unpublished', nullable=False)
    nps = db.Column(db.Float, nullable=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'))

    manager = db.relationship('Contact', foreign_keys=[manager_id], backref='managed_meetings')
    club = db.relationship('Club', foreign_keys=[club_id], backref='meetings')

    best_table_topic_speaker = db.relationship(
        'Contact', foreign_keys=[best_table_topic_id])
    best_evaluator = db.relationship(
        'Contact', foreign_keys=[best_evaluator_id])
    best_speaker = db.relationship('Contact', foreign_keys=[best_speaker_id])
    best_role_taker = db.relationship(
        'Contact', foreign_keys=[best_role_taker_id])
    media = db.relationship('Media', foreign_keys=[media_id])

    def get_best_award_ids(self):
        """
        Gets the set of best award IDs for this meeting.
        
        Returns:
            set: Set of award IDs
        """
        return {
            award_id for award_id in [
                self.best_table_topic_id,
                self.best_evaluator_id,
                self.best_speaker_id,
                self.best_role_taker_id
            ] if award_id
        }

    def delete_full(self):
        """
        Deletes the meeting and all associated data in the correct order.
        Returns:
            tuple: (success (bool), message (str or None))
        """
        from .roster import Waitlist, Roster
        from .session import SessionLog
        from .voting import Vote
        
        try:
            # 1. Delete Waitlist entries
            Waitlist.delete_for_meeting(self.Meeting_Number)

            # 2. Delete SessionLog entries
            SessionLog.delete_for_meeting(self.Meeting_Number)

            # 3. Delete Roster and RosterRole entries
            Roster.delete_for_meeting(self.Meeting_Number)

            # 4. Delete Vote entries
            Vote.delete_for_meeting(self.Meeting_Number)

            # 5. Handle Meeting's Media
            if self.media_id:
                media_to_delete = self.media
                self.media_id = None # Break the link first
                db.session.delete(media_to_delete)

            # 6. Delete the Meeting itself
            db.session.delete(self)
            
            db.session.commit()
            return True, None
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)
