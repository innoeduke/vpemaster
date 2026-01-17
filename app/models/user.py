"""User model for authentication and authorization."""
from flask_login import UserMixin, AnonymousUserMixin
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
    Status = db.Column(db.String(50), nullable=False, default='active')
    
    # Additional member information
    member_no = db.Column(db.String(50), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    dtm = db.Column(db.Boolean, default=False, nullable=False)
    avatar_url = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    
    # Relationships
    contact = db.relationship('Contact', foreign_keys=[Contact_ID], backref=db.backref('user', uselist=False))
    roles = db.relationship(
        'app.models.role.Role',
        secondary='user_clubs',
        back_populates='users',
        lazy='joined',
        primaryjoin='User.id == UserClub.user_id',
        secondaryjoin='app.models.role.Role.id == UserClub.club_role_id',
        viewonly=True
    )
    
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
    
    @property
    def primary_role(self):
        """Returns the user's highest-level role."""
        if not self.roles:
            return None
        return max(self.roles, key=lambda r: r.level if r.level is not None else 0)

    @property
    def primary_role_name(self):
        """Returns the name of the user's highest-level role."""
        role = self.primary_role
        return role.name if role else "User"

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
    
    def can(self, permission):
        """Check if user has a permission."""
        return self.has_permission(permission)


class AnonymousUser(AnonymousUserMixin):
    """Anonymous user with Guest role permissions."""
    
    _permission_cache = None

    def get_permissions(self):
        """Get permissions for Guest role."""
        if self._permission_cache is None:
            # Import here to avoid circular dependencies
            from .role import Role
            
            guest_role = Role.get_by_name('Guest')
            permissions = set()
            if guest_role:
                for permission in guest_role.permissions:
                    permissions.add(permission.name)
            
            self._permission_cache = permissions
        
        return self._permission_cache

    def has_permission(self, permission_name):
        """Check if guest has a specific permission."""
        return permission_name in self.get_permissions()

    def can(self, permission):
        return self.has_permission(permission)

    @property
    def primary_role_name(self):
        return 'Guest'
