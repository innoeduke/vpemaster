"""Role model for authorization system."""
from datetime import datetime, timezone
from .base import db


class Role(db.Model):
    """Represents a role that can be assigned to users."""
    __tablename__ = 'auth_roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    level = db.Column(db.Integer)  # For hierarchy: Admin=8, VPE=4, Officer=2, Member=1
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    permissions = db.relationship('Permission', secondary='role_permissions', back_populates='roles')
    users = db.relationship(
        'User',
        secondary='user_clubs',
        back_populates='roles',
        primaryjoin='Role.id == UserClub.club_role_id',
        secondaryjoin='User.id == UserClub.user_id',
        viewonly=True
    )
    
    def __repr__(self):
        return f'<Role {self.name}>'
    
    @staticmethod
    def get_by_name(name):
        """Get role by name."""
        return Role.query.filter_by(name=name).first()
    
    def has_permission(self, permission_name):
        """Check if this role has a specific permission."""
        return any(p.name == permission_name for p in self.permissions)
    
    def add_permission(self, permission):
        """Add a permission to this role."""
        if permission not in self.permissions:
            self.permissions.append(permission)
    
    def remove_permission(self, permission):
        """Remove a permission from this role."""
        if permission in self.permissions:
            self.permissions.remove(permission)
