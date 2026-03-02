from .. import db

class VerificationTask(db.Model):
    """
    Model for tracking asynchronous blockchain verification tasks.
    This replaces the in-memory dictionary to support multi-worker environments.
    """
    __tablename__ = 'verification_tasks'
    
    id = db.Column(db.String(36), primary_key=True)  # UUID
    status = db.Column(db.String(20), default='pending')
    result = db.Column(db.JSON, nullable=True)
    params = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.Float, nullable=False)  # Unix timestamp

    def __repr__(self):
        return f'<VerificationTask {self.id} status={self.status}>'
