"""Permission model for authorization system."""
from datetime import datetime
from .base import db


class Permission(db.Model):
    """Represents a permission that can be assigned to roles."""
    __tablename__ = 'permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), index=True)  # e.g., 'agenda', 'booking', 'settings'
    resource = db.Column(db.String(50))  # e.g., 'agenda', 'booking', 'speech_logs'
    action = db.Column(db.String(50))    # e.g., 'edit', 'view', 'assign', 'delete'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    roles = db.relationship('app.models.role.Role', secondary='role_permissions', back_populates='permissions')
    
    def __repr__(self):
        return f'<Permission {self.name}>'
    
    @staticmethod
    def get_by_name(name):
        """Get permission by name."""
        return Permission.query.filter_by(name=name).first()
    
    @staticmethod
    def get_by_category(category):
        """Get all permissions in a category."""
        return Permission.query.filter_by(category=category).order_by(Permission.name).all()
