from datetime import datetime
from .base import db

class ChatMessage(db.Model):
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)       # 'user', 'assistant', 'system'
    content = db.Column(db.Text, nullable=False)           # message text
    tool_calls = db.Column(db.Text, nullable=True)        # JSON string of tool calls made
    mode = db.Column(db.String(10), nullable=False)        # 'ai' or 'command'
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    # Relationships
    user = db.relationship('User', backref=db.backref('chat_messages', lazy=True, cascade='all, delete-orphan'))
    club = db.relationship('Club', backref=db.backref('chat_messages', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<ChatMessage {self.id} role={self.role} mode={self.mode} user={self.user_id}>'
