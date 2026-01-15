"""User model for authentication and authorization."""
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app

from .base import db


class User(UserMixin, db.Model):
    __tablename__ = 'Users'
    id = db.Column(db.Integer, primary_key=True)
    Username = db.Column(db.String(50), nullable=False, unique=True)
    Email = db.Column(db.String(120), unique=True, nullable=True)
    # Migrated to Contact: Member_ID, Mentor_ID, Current_Path, Next_Project, credentials
    Contact_ID = db.Column(db.Integer, db.ForeignKey(
        'Contacts.id'), nullable=True, unique=True)
    Pass_Hash = db.Column(db.String(255), nullable=False)
    Date_Created = db.Column(db.Date)
    Role = db.Column(db.String(50), nullable=False, default='Member')  # DEPRECATED: Will be removed after migration
    Status = db.Column(db.String(50), nullable=False, default='active')
    
    # Relationships
    contact = db.relationship('Contact', foreign_keys=[Contact_ID], backref=db.backref('user', uselist=False))
    roles = db.relationship('app.models.role.Role', secondary='user_roles', back_populates='users', lazy='joined', foreign_keys='[UserRole.user_id, UserRole.role_id]')
    
    # Cache for permissions to avoid repeated queries
    _permission_cache = None

    def set_password(self, password):
        self.Pass_Hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.Pass_Hash, password)

    def get_reset_token(self, expires_sec=1800):
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id})

    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, max_age=expires_sec).get('user_id')
        except:
            return None
        return db.session.get(User, user_id)
    
    # Permission system methods
    
    def get_permissions(self):
        """Get all permissions for this user from their roles."""
        if self._permission_cache is None:
            permissions = set()
            for role in self.roles:
                for permission in role.permissions:
                    permissions.add(permission.name)
            self._permission_cache = permissions
        return self._permission_cache
    
    def has_permission(self, permission_name):
        """Check if user has a specific permission."""
        return permission_name in self.get_permissions()
    
    def has_role(self, role_name):
        """Check if user has a specific role."""
        return any(role.name == role_name for role in self.roles)
    
    def add_role(self, role):
        """Add a role to this user."""
        if role not in self.roles:
            self.roles.append(role)
            self._permission_cache = None  # Clear cache
    
    def remove_role(self, role):
        """Remove a role from this user."""
        if role in self.roles:
            self.roles.remove(role)
            self._permission_cache = None  # Clear cache
    
    # Legacy methods - will be updated/removed during migration
    
    def can(self, permission):
        """Check if user has a permission. Updated to use new permission system."""
        # Try new permission system first
        if self.roles:
            return self.has_permission(permission)
        
        # Fallback to old system during migration
        from ..auth.utils import ROLE_PERMISSIONS 
        role = self.Role if self.Role else "Guest"
        return permission in ROLE_PERMISSIONS.get(role, set())

    @property
    def is_admin(self):
        """Check if user is admin. Will be removed - use has_role('Admin') instead."""
        # Try new system first
        if self.roles:
            return self.has_role('Admin')
        # Fallback to old system
        return self.Role == 'Admin'

    @property
    def is_officer(self):
        """Check if user is officer. Will be removed - use has_role() instead."""
        # Try new system first
        if self.roles:
            return self.has_role('Officer') or self.has_role('VPE') or self.has_role('Admin')
        # Fallback to old system
        return self.Role in ['Officer', 'Admin', 'VPE']
