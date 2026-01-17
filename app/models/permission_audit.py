from datetime import datetime, timezone
from .base import db

class PermissionAudit(db.Model):
    __tablename__ = 'permission_audits'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    admin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # 'ASSIGN_ROLE', 'REMOVE_ROLE', 'UPDATE_ROLE_PERMS'
    target_type = db.Column(db.String(50), nullable=False)  # 'USER', 'ROLE'
    target_id = db.Column(db.Integer, nullable=False)
    target_name = db.Column(db.String(100))
    changes = db.Column(db.Text)  # JSON or descriptive string

    admin = db.relationship('User', foreign_keys=[admin_id])

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'admin_name': self.admin.contact.Name if self.admin and self.admin.contact else self.admin.username,
            'action': self.action,
            'target_type': self.target_type,
            'target_name': self.target_name,
            'changes': self.changes
        }
