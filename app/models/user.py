"""User model for authentication and authorization."""
from flask_login import UserMixin, AnonymousUserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app

from .base import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    # Migrated to Contact: Member_ID, Mentor_ID, Current_Path, Next_Project, credentials
    # contact_id removed as it's now club-specific in UserClub
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.Date)
    status = db.Column(db.String(50), nullable=False, default='active')
    
    # Additional member information
    member_no = db.Column(db.String(50), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    dtm = db.Column(db.Boolean, default=False, nullable=False)
    avatar_url = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    
    # Relationships
    # contact relationship removed, use UserClub.contact instead
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
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

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

    def get_user_club(self, club_id):
        """Get the UserClub record for a specific club."""
        from .user_club import UserClub
        if not club_id:
            return None
        return UserClub.query.filter_by(user_id=self.id, club_id=club_id).first()

    def get_contact(self, club_id=None):
        """Get the contact record for this user in a specific club."""
        from ..club_context import get_current_club_id
        
        # Optimization: Check if batch-populated for the current club
        current_club_id = get_current_club_id()
        if (not club_id or club_id == current_club_id) and getattr(self, '_current_contact', None):
            return self._current_contact
            
        if not club_id:
            club_id = current_club_id
        
        if club_id:
            uc = self.get_user_club(club_id)
            if uc:
                return uc.contact
            
        # Fallback for cases where no club ID is resolved: 
        # Return the first available contact this user is associated with.
        from .user_club import UserClub
        uc = UserClub.query.filter_by(user_id=self.id).first()
        return uc.contact if uc else None

    @property
    def contact(self):
        """
        Ambiguous property for backward compatibility. 
        Returns the contact for the current club context.
        """
        return self.get_contact()

    @property
    def contact_id(self):
        """
        Returns the contact ID for the current club context.
        """
        contact = self.contact
        return contact.id if contact else None

    @staticmethod
    def populate_contacts(users, club_id=None):
        """
        Batch-populates contact records for a list of users for a specific club.
        Adds a _current_contact attribute to each user object to avoid N+1 queries.
        """
        if not users:
            return
            
        from .user_club import UserClub
        from ..club_context import get_current_club_id
        
        if not club_id:
            club_id = get_current_club_id()
            
        user_ids = [u.id for u in users]
        ucs = UserClub.query.filter(
            UserClub.user_id.in_(user_ids),
            UserClub.club_id == club_id
        ).options(db.joinedload(UserClub.contact)).all()
        
        # Map user_id to contact
        contact_map = {uc.user_id: uc.contact for uc in ucs}
        
        # Set a transient attribute on users
        for user in users:
            user._current_contact = contact_map.get(user.id)

    def ensure_contact(self, full_name=None, first_name=None, last_name=None, email=None, phone=None, club_id=None):
        """
        Ensure the user has an associated contact record for the given club.
        """
        from datetime import date
        from .contact import Contact
        from .contact_club import ContactClub
        from .club import Club
        from .user_club import UserClub
        from ..club_context import get_current_club_id

        if not club_id:
             club_id = get_current_club_id()
             if not club_id:
                 default_club = Club.query.first()
                 club_id = default_club.id if default_club else None
        
        if not club_id:
            return None

        # Name construction
        if not full_name and (first_name or last_name):
            full_name = f"{first_name or ''} {last_name or ''}".strip()
        final_name = full_name or self.username

        uc = self.get_user_club(club_id)
        contact = uc.contact if uc else None

        if contact is None:
             # Create new contact
             contact = Contact(
                 Name=final_name,
                 first_name=first_name,
                 last_name=last_name,
                 Email=email or self.email,
                 Phone_Number=phone or self.phone,
                 Type='Member',
                 Date_Created=date.today()
             )
             db.session.add(contact)
             db.session.flush()
             
             if uc:
                 uc.contact_id = contact.id
             else:
                 uc = UserClub(
                     user_id=self.id,
                     club_id=club_id,
                     contact_id=contact.id
                 )
                 db.session.add(uc)
             
             # Also link via ContactClub for roster/contact management
             contact_club = ContactClub.query.filter_by(contact_id=contact.id, club_id=club_id).first()
             if not contact_club:
                 db.session.add(ContactClub(contact_id=contact.id, club_id=club_id))
        else:
             # Sync to existing contact
             if full_name: contact.Name = full_name
             if first_name: contact.first_name = first_name
             if last_name: contact.last_name = last_name
             if email: contact.Email = email
             if phone: contact.Phone_Number = phone
             
             # Ensure contact is linked to club via ContactClub
             exists = ContactClub.query.filter_by(contact_id=contact.id, club_id=club_id).first()
             if not exists:
                 db.session.add(ContactClub(contact_id=contact.id, club_id=club_id))
        
        return contact

    def set_club_role(self, club_id, role_id):
        """
        Set the user's role for a specific club using UserClub.
        """
        from .user_club import UserClub
        from .club import Club
        from ..club_context import get_current_club_id
        
        if not club_id:
             club_id = get_current_club_id()
             if not club_id:
                 default_club = Club.query.first()
                 club_id = default_club.id if default_club else None
        
        if not club_id or not role_id:
            return

        user_clubs = UserClub.query.filter_by(user_id=self.id).all()
        
        # Check if we already have a record for this club
        existing_uc = None
        for uc in user_clubs:
            if uc.club_id == club_id:
                existing_uc = uc
                break
        
        if existing_uc:
            existing_uc.club_role_id = role_id
        else:
            new_uc = UserClub(
                user_id=self.id,
                club_id=club_id,
                club_role_id=role_id
            )
            # contact_id will be set by UserClub.__init__ or ensure_contact
            db.session.add(new_uc)



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
