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
    Role = db.Column(db.String(50), nullable=False, default='Member')
    Status = db.Column(db.String(50), nullable=False, default='active')
    
    contact = db.relationship('Contact', foreign_keys=[Contact_ID], backref=db.backref('user', uselist=False))

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

    def can(self, permission):
        # Local import to avoid circular dependency
        from ..auth.utils import ROLE_PERMISSIONS 
        
        # If user role is None, treat as Guest
        role = self.Role if self.Role else "Guest"
        return permission in ROLE_PERMISSIONS.get(role, set())

    @property
    def is_admin(self):
        return self.Role == 'Admin'

    @property
    def is_officer(self):
        return self.Role in ['Officer', 'Admin', 'VPE']
