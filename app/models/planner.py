"""Planner model for user speech and role-taking plans."""
from datetime import datetime
from .base import db


class Planner(db.Model):
    __tablename__ = 'planner'
    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('Meetings.id'), nullable=True, index=True)
    @property
    def meeting_number(self):
        if self.meeting:
            return self.meeting.Meeting_Number
        return None
    meeting_role_id = db.Column(db.Integer, db.ForeignKey('meeting_roles.id'), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('Projects.id'), nullable=True)
    status = db.Column(db.String(20), default='draft', nullable=False)
    notes = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), index=True, nullable=False)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), index=True, nullable=True)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    date_modified = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('planner_entries', lazy='dynamic'))
    club = db.relationship('Club', backref='planner_entries')
    role = db.relationship('MeetingRole', backref='planner_entries')
    project = db.relationship('Project', backref='planner_entries')
    
    @classmethod
    def delete_for_meeting(cls, meeting_id):
        """Deletes all planner entries for a specific meeting."""
        cls.query.filter_by(meeting_id=meeting_id).delete(synchronize_session=False)

    def __repr__(self):
        return f'<Planner {self.id} user_id={self.user_id} status={self.status}>'
