from datetime import datetime, timezone
from .base import db


class Issue(db.Model):
    __tablename__ = 'issues'

    id = db.Column(db.Integer, primary_key=True)

    TYPE_BUG = 'bug'
    TYPE_FEATURE = 'feature'
    TYPE_TASK = 'task'
    TYPES = (TYPE_BUG, TYPE_FEATURE, TYPE_TASK)

    STATUS_OPEN = 'open'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_CLOSED = 'closed'
    STATUS_REJECTED = 'rejected'
    STATUS_CANCELLED = 'cancelled'
    STATUSES = (STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_CLOSED,
                STATUS_REJECTED, STATUS_CANCELLED)
    TERMINAL_STATUSES = (STATUS_CLOSED, STATUS_REJECTED, STATUS_CANCELLED)

    PRIORITY_HIGH = 'high'
    PRIORITY_MEDIUM = 'medium'
    PRIORITY_LOW = 'low'
    PRIORITIES = (PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW)

    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=False, index=True)
    type = db.Column(db.String(20), nullable=False, default=TYPE_BUG)
    status = db.Column(db.String(20), nullable=False, default=STATUS_OPEN)
    priority = db.Column(db.String(10), nullable=False, default=PRIORITY_MEDIUM)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)

    submitter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    assignee_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    closed_at = db.Column(db.DateTime, nullable=True)

    submitter = db.relationship('User', foreign_keys=[submitter_id], backref='submitted_issues')
    assignee = db.relationship('User', foreign_keys=[assignee_id], backref='assigned_issues')
    club = db.relationship('Club', backref='issues')
    comments = db.relationship(
        'IssueComment',
        backref='issue',
        cascade='all, delete-orphan',
        order_by='IssueComment.created_at',
    )

    __table_args__ = (
        db.Index('ix_issues_club_created', 'club_id', 'created_at'),
    )

    def is_terminal(self):
        return self.status in self.TERMINAL_STATUSES

    def __repr__(self):
        return f'<Issue {self.id} {self.type}/{self.status}>'


class IssueComment(db.Model):
    __tablename__ = 'issue_comments'

    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey('issues.id'), nullable=False, index=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    author = db.relationship('User', backref='issue_comments')

    def __repr__(self):
        return f'<IssueComment {self.id} on issue {self.issue_id}>'
