"""Meeting model."""
import os
from sqlalchemy.dialects import mysql
from .base import db


def generate_type_to_template():
    """
    Dynamically generate the TYPE_TO_TEMPLATE mapping by listing CSV files
    in the mtg_templates folder and converting filenames to title case.
    
    Returns:
        dict: Mapping of theme names to template filenames.
              e.g., {'Keynote Speech': 'keynote_speech.csv', ...}
    """
    templates_dir = os.path.join(
        os.path.dirname(__file__), '..', 'static', 'mtg_templates'
    )
    
    type_to_template = {}
    
    try:
        for filename in os.listdir(templates_dir):
            if filename.endswith('.csv') and not filename.startswith('.'):
                # Convert filename to theme name: 'keynote_speech.csv' -> 'Keynote Speech'
                theme_name = filename[:-4].replace('_', ' ').title()
                type_to_template[theme_name] = filename
    except OSError:
        # Fallback to static mapping if directory cannot be read
        type_to_template = {
            'Keynote Speech': 'keynote_speech.csv',
            'Speech Marathon': 'speech_marathon.csv',
            'Speech Contest': 'speech_contest.csv',
            'Panel Discussion': 'panel_discussion.csv',
            'Debate': 'debate.csv',
            'Pecha Kucha': 'pecha_kucha.csv',
            'Gavel Passing': 'gavel_passing.csv',
            'Club Election': 'club_election.csv'
        }
    
    return type_to_template


class Meeting(db.Model):
    __tablename__ = 'Meetings'
    
    # Meeting Type Mapping to Template Files (dynamically generated)
    TYPE_TO_TEMPLATE = generate_type_to_template()

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
    excomm_id = db.Column(db.Integer, db.ForeignKey('excomm.id'), nullable=True, index=True)

    manager = db.relationship('Contact', foreign_keys=[manager_id], backref='managed_meetings')
    club = db.relationship('Club', foreign_keys=[club_id], back_populates='meetings')
    excomm = db.relationship('ExComm', backref='meetings')

    best_table_topic_speaker = db.relationship(
        'Contact', foreign_keys=[best_table_topic_id])
    best_evaluator = db.relationship(
        'Contact', foreign_keys=[best_evaluator_id])
    best_speaker = db.relationship('Contact', foreign_keys=[best_speaker_id])
    best_role_taker = db.relationship(
        'Contact', foreign_keys=[best_role_taker_id])
    media = db.relationship('Media', foreign_keys=[media_id])
    
    def sync_excomm(self, force=False):
        """
        Synchronizes the excomm_id for the meeting.
        """
        if not self.excomm_id or force:
            excomm = self.get_excomm()
            if excomm:
                self.excomm_id = excomm.id
                return True
        return False

    def get_excomm(self):
        """
        Resolves the correct ExComm for this meeting.
        Priority:
        1. Linked excomm_id
        2. Date-based resolution
        3. Most recent as fallback
        """
        if self.excomm:
            return self.excomm
        
        from .excomm import ExComm
        if self.Meeting_Date:
            excomm = ExComm.query.filter(
                ExComm.club_id == self.club_id,
                ExComm.start_date <= self.Meeting_Date,
                ExComm.end_date >= self.Meeting_Date
            ).first()
            if excomm:
                return excomm
                
        # Final fallback: most recent
        return ExComm.query.filter_by(club_id=self.club_id).order_by(ExComm.start_date.desc()).first()

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
