"""Media model for storing media URLs and notes."""
from .base import db


class Media(db.Model):
    __tablename__ = 'Media'
    id = db.Column(db.Integer, primary_key=True)
    log_id = db.Column(db.Integer, db.ForeignKey(
        'Session_Logs.id', ondelete='SET NULL'), nullable=True)
    url = db.Column(db.String(1024), nullable=True)
    notes = db.Column(db.Text, nullable=True)
