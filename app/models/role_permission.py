"""Association table for Role-Permission many-to-many relationship."""
from .base import db


class RolePermission(db.Model):
    """Association table linking roles to permissions."""
    __tablename__ = 'role_permissions'
    
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('auth_roles.id', ondelete='CASCADE'), nullable=False)
    permission_id = db.Column(db.Integer, db.ForeignKey('permissions.id', ondelete='CASCADE'), nullable=False)
    
    # Unique constraint to prevent duplicate role-permission assignments
    __table_args__ = (
        db.UniqueConstraint('role_id', 'permission_id', name='unique_role_permission'),
    )
    
    def __repr__(self):
        return f'<RolePermission role_id={self.role_id} permission_id={self.permission_id}>'
