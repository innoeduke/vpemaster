"""Models for generalized programs and enrollments."""
from datetime import datetime, timezone
from .base import db


class Program(db.Model):
    __tablename__ = 'programs'

    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id', ondelete='CASCADE'), nullable=True, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    club = db.relationship('Club', backref=db.backref('programs', cascade='all, delete-orphan', lazy='dynamic'))
    creator = db.relationship('User', foreign_keys=[created_by_id])
    tasks = db.relationship('ProgramTask', order_by='ProgramTask.display_order, ProgramTask.id', cascade='all, delete-orphan', back_populates='program')

    def __repr__(self):
        return f'<Program {self.name} (id={self.id})>'


class ProgramTask(db.Model):
    __tablename__ = 'program_tasks'

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    phase_label = db.Column(db.String(60), nullable=True)
    display_order = db.Column(db.Integer, default=0, nullable=False)
    completion_type = db.Column(db.String(30), nullable=False)  # 'manual', 'sessionlog', etc.
    completion_config = db.Column(db.JSON, nullable=True)
    is_required = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    program = db.relationship('Program', back_populates='tasks')

    def __repr__(self):
        return f'<ProgramTask {self.title} (program_id={self.program_id})>'


class ProgramEnrollment(db.Model):
    __tablename__ = 'program_enrollments'

    id = db.Column(db.Integer, primary_key=True)
    program_id = db.Column(db.Integer, db.ForeignKey('programs.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)  # mentee
    mentor_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    mentor_contact_id = db.Column(db.Integer, db.ForeignKey('Contacts.id', ondelete='SET NULL'), nullable=True, index=True)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id', ondelete='CASCADE'), nullable=False, index=True)
    status = db.Column(db.String(20), default='active', nullable=False)  # 'active', 'paused', 'completed', 'cancelled'
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Unique constraint per club/user/program
    __table_args__ = (
        db.UniqueConstraint('program_id', 'user_id', 'club_id', name='uq_program_enrollment_user_club'),
    )

    # Relationships
    program = db.relationship('Program', backref=db.backref('enrollments_rel', cascade='all, delete-orphan', lazy='dynamic'))
    mentee = db.relationship('User', foreign_keys=[user_id], backref=db.backref('program_enrollments_rel', cascade='all, delete-orphan', lazy='dynamic'))
    mentor = db.relationship('User', foreign_keys=[mentor_user_id])
    mentor_contact = db.relationship('Contact', foreign_keys=[mentor_contact_id])
    club = db.relationship('Club', backref=db.backref('program_enrollments_rel', cascade='all, delete-orphan', lazy='dynamic'))
    creator = db.relationship('User', foreign_keys=[created_by_id])
    planner_entries = db.relationship('Planner', backref='enrollment', cascade='all, delete-orphan', lazy='dynamic')

    def __repr__(self):
        return f'<ProgramEnrollment program_id={self.program_id} user_id={self.user_id} club_id={self.club_id}>'
