"""Meeting model."""
from sqlalchemy.dialects import mysql
from sqlalchemy import event
from .base import db


class Meeting(db.Model):
    __tablename__ = 'Meetings'

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=False, index=True)
    type = db.Column(db.String(255), default='Keynote Speech')
    # Meeting_Number is a per-club counter. Two meetings in different clubs
    # can share the same number; two meetings in the SAME club cannot.
    # The DB-level invariant is enforced by uq_meetings_club_number below.
    Meeting_Number = db.Column(mysql.SMALLINT(unsigned=True), nullable=False)
    Meeting_Date = db.Column(db.Date)
    Meeting_Title = db.Column(db.String(255))
    Subtitle = db.Column(db.String(255), nullable=True)
    Start_Time = db.Column(db.Time)
    Meeting_Template = db.Column(db.String(100))
    WOD = db.Column(db.String(100))

    media_id = db.Column(db.Integer, db.ForeignKey('Media.id', use_alter=True))
    ge_mode = db.Column(db.Integer, default=0)
    poster_url = db.Column(db.String(500), nullable=True)
    status = db.Column(db.Enum('unpublished', 'not started', 'running', 'finished', 'cancelled', name='meeting_status'),
                       default='unpublished', nullable=False)
    nps = db.Column(db.Float, nullable=True)
    sharing_master_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    excomm_id = db.Column(db.Integer, db.ForeignKey('excomm.id'), nullable=True, index=True)

    __table_args__ = (
        db.UniqueConstraint('club_id', 'Meeting_Number', name='uq_meetings_club_number'),
    )

    sharing_master = db.relationship('Contact', foreign_keys=[sharing_master_id], backref='shared_meetings')
    club = db.relationship('Club', foreign_keys=[club_id], back_populates='meetings')
    excomm = db.relationship('ExComm', backref='meetings')

    def update_sharing_master(self):
        """
        Sets sharing_master_id to the contact id of the first owner of the first "Featured Session"
        """
        featured_logs = [log for log in self.session_logs if log.session_type and log.session_type.Featured]
        featured_logs.sort(key=lambda x: x.Meeting_Seq or 0)
        
        new_master_id = None
        if featured_logs:
            first_featured = featured_logs[0]
            if first_featured.owners:
                new_master_id = first_featured.owners[0].id
                
        self.sharing_master_id = new_master_id

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

    def _get_first_winner_id(self, category):
        for w in self.award_winners:
            if w.award_category == category:
                return w.contact_id
        return None

    def _get_first_winner_contact(self, category):
        for w in self.award_winners:
            if w.award_category == category:
                return w.contact
        return None

    @property
    def best_speaker_id(self):
        return self._get_first_winner_id('speaker')

    @best_speaker_id.setter
    def best_speaker_id(self, value):
        from .voting import MeetingAwardWinner
        if self.id is None:
            # Meeting is not yet flushed; defer the record creation by
            # removing any previously stored value and queueing the new one
            # via a SQLAlchemy after_insert event.
            self._pending_best_speaker_id = value
            return
        MeetingAwardWinner.query.filter_by(meeting_id=self.id, award_category='speaker').delete()
        if value is not None:
            db.session.add(MeetingAwardWinner(meeting_id=self.id, award_category='speaker', contact_id=value))

    @property
    def best_speaker(self):
        return self._get_first_winner_contact('speaker')

    @property
    def best_evaluator_id(self):
        return self._get_first_winner_id('evaluator')

    @property
    def best_evaluator(self):
        return self._get_first_winner_contact('evaluator')

    @property
    def best_table_topic_id(self):
        return self._get_first_winner_id('table-topic')

    @property
    def best_table_topic_speaker(self):
        return self._get_first_winner_contact('table-topic')

    @property
    def best_role_taker_id(self):
        return self._get_first_winner_id('role-taker')

    @property
    def best_role_taker(self):
        return self._get_first_winner_contact('role-taker')

    @property
    def best_debater_id(self):
        return self._get_first_winner_id('debater')

    @property
    def best_debater(self):
        return self._get_first_winner_contact('debater')

    @property
    def lucky_draw_winner_id(self):
        return self._get_first_winner_id('lucky_draw')

    @property
    def lucky_draw_winner(self):
        return self._get_first_winner_contact('lucky_draw')

    def get_best_award_ids(self):
        """
        Gets the set of best award IDs for this meeting.
        
        Returns:
            set: Set of award IDs
        """
        return {w.contact_id for w in self.award_winners}

    def delete_full(self):
        """
        Deletes the meeting and all associated data in the correct order.
        Returns:
            tuple: (success (bool), message (str or None))
        """
        from .roster import Waitlist, Roster
        from .session import SessionLog
        from .voting import Vote
        from .planner import Planner
        
        try:
            meeting_id = self.id
            target_club_id = self.club_id
            target_number = self.Meeting_Number
            
            Waitlist.delete_for_meeting(meeting_id)
            SessionLog.delete_for_meeting(meeting_id)
            Roster.delete_for_meeting(meeting_id)
            Vote.delete_for_meeting(meeting_id)
            Planner.delete_for_meeting(meeting_id)

            db.session.flush()
            
            if self.media_id:
                media_to_delete = self.media
                self.media_id = None # Break the link first
                db.session.delete(media_to_delete)

            db.session.delete(self)
            db.session.flush()

            subsequent_meetings = Meeting.query.filter(
                Meeting.club_id == target_club_id,
                Meeting.Meeting_Number > target_number
            ).order_by(Meeting.Meeting_Number.asc()).all()

            for m in subsequent_meetings:
                # Finally update the meeting itself
                m.Meeting_Number = m.Meeting_Number - 1
            
            db.session.commit()
            return True, None
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)


@event.listens_for(Meeting, 'after_insert')
def _apply_pending_best_speaker_id(mapper, connection, target):
    """Flush any best_speaker_id that was set before the meeting had an id."""
    pending = getattr(target, '_pending_best_speaker_id', None)
    if pending is not None and target.id is not None:
        from .voting import MeetingAwardWinner
        connection.execute(
            MeetingAwardWinner.__table__.insert().values(
                meeting_id=target.id,
                award_category='speaker',
                contact_id=pending,
            )
        )
        target._pending_best_speaker_id = None
