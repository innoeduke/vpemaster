"""Role model for authorization system."""
from datetime import datetime, timezone
from .base import db


class Role(db.Model):
    """Represents a role that can be assigned to users."""
    __tablename__ = 'auth_roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.Text)
    level = db.Column(db.Integer)  # For hierarchy: SysAdmin=8, ClubAdmin=4, Operator=3, Staff=2, Member=1
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id', ondelete='CASCADE'), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        db.UniqueConstraint('club_id', 'name', name='uq_club_role_name'),
    )

    # Relationships
    permissions = db.relationship('Permission', secondary='role_permissions', back_populates='roles', lazy='joined')
    
    def __repr__(self):
        return f'<Role {self.name}>'
    
    _all_roles_cache = None
    _name_cache = {}

    @staticmethod
    def get_by_name(name):
        """Get role by name, using cache if available."""
        role = Role._name_cache.get(name)
        if role:
            return db.session.merge(role, load=False)
        
        role = Role.query.filter_by(name=name).first()
        if role:
            Role._name_cache[name] = role
        return role

    @staticmethod
    def get_all_cached():
        """Get all roles, using cache if available."""
        if Role._all_roles_cache is None:
            Role._all_roles_cache = Role.query.all()
            # Also populate name cache while we are at it
            for r in Role._all_roles_cache:
                Role._name_cache[r.name] = r
            return Role._all_roles_cache
        
        return [db.session.merge(r, load=False) for r in Role._all_roles_cache]
    
    def has_permission(self, permission_name, club_id=None):
        """Check if this role has a specific permission.

        When ``club_id`` is given, consults the per-club role_permissions
        mapping (a single explicit query). When ``club_id`` is None, falls
        back to the (cached, joined) ``self.permissions`` relationship which
        is the union across all clubs — the legacy global behavior, kept
        for backward compatibility with code paths that don't have a club
        context (e.g. some test fixtures, identity-loader cache priming).
        """
        if club_id is None:
            return any(p.name == permission_name for p in self.permissions)

        from .permission import Permission
        from .role_permission import RolePermission

        perm_id = db.session.query(Permission.id).filter_by(name=permission_name).scalar()
        if perm_id is None:
            return False
        return db.session.query(RolePermission.id).filter_by(
            role_id=self.id, permission_id=perm_id, club_id=club_id
        ).first() is not None
    
    def add_permission(self, permission):
        """Add a permission to this role."""
        if permission not in self.permissions:
            self.permissions.append(permission)
    
    def remove_permission(self, permission):
        """Remove a permission from this role."""
        if permission in self.permissions:
            self.permissions.remove(permission)

    @staticmethod
    def clear_role_cache():
        """Clear all role caches."""
        Role._all_roles_cache = None
        Role._name_cache = {}
