"""User model for authentication and authorization."""
from flask_login import UserMixin, AnonymousUserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app
from sqlalchemy import event

from .base import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    _first_name = db.Column('first_name', db.String(100), nullable=True)
    _last_name = db.Column('last_name', db.String(100), nullable=True)
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
    
    @property
    def first_name(self):
        return self._first_name
    
    @first_name.setter
    def first_name(self, value):
        self._first_name = value
        # Sync to contact if in a session and contact exists
        try:
            contact = self.get_contact()
            if contact and contact.first_name != value:
                contact.first_name = value
                contact.update_name_from_parts(overwrite=True)
        except:
            pass

    @property
    def last_name(self):
        return self._last_name
    
    @last_name.setter
    def last_name(self, value):
        self._last_name = value
        # Sync to contact if in a session and contact exists
        try:
            contact = self.get_contact()
            if contact and contact.last_name != value:
                contact.last_name = value
                contact.update_name_from_parts(overwrite=True)
        except:
            pass
    
    # Relationships
    messages_sent = db.relationship('Message',
                                    foreign_keys='Message.sender_id',
                                    backref='sender', lazy='dynamic')
    messages_received = db.relationship('Message',
                                        foreign_keys='Message.recipient_id',
                                        backref='recipient', lazy='dynamic')
    # contact relationship removed, use UserClub.contact instead
    # Actually, lines 71-79 covers roles relationship. first_name lines are 32-45.
    roles = db.relationship(
        'app.models.role.Role',
        secondary='user_clubs',
        back_populates='users',
        lazy='joined',
        primaryjoin='User.id == UserClub.user_id',
        secondaryjoin='(UserClub.club_role_level.op("&")(app.models.role.Role.level)) == app.models.role.Role.level',
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
    
    @property
    def is_sysadmin(self):
        """Check if user has SysAdmin role (globally/platform-wide)."""
        from ..auth.permissions import Permissions
        return self.has_role(Permissions.SYSADMIN)

    def is_club_admin(self, club_id=None):
        """Check if user is a ClubAdmin for the specified club."""
        from .role import Role
        from .user_club import UserClub
        from ..auth.permissions import Permissions
        from ..club_context import get_current_club_id
        
        if not club_id:
            club_id = get_current_club_id()
        
        if not club_id:
            return False
            
        club_role = Role.get_by_name(Permissions.CLUBADMIN)
        if not club_role:
            return False
            
        uc = UserClub.query.filter_by(user_id=self.id, club_id=club_id).first()
        if not uc:
            return False
            
        return (uc.club_role_level & club_role.level) == club_role.level

    def get_roles_for_club(self, club_id):
        """Get all roles for this user in a specific club context."""
        from .user_club import UserClub
        from ..auth.permissions import Permissions
        
        roles_list = []
        
        # 1. Global SysAdmin check: SysAdmins are admins everywhere
        if self.is_sysadmin:
            roles_list.append(Permissions.SYSADMIN)
            
        # 2. Club-specific roles
        uc = UserClub.query.filter_by(user_id=self.id, club_id=club_id).first()
        if uc:
            # Base 'User' role for any membership
            if Permissions.USER not in roles_list:
                roles_list.append(Permissions.USER)
                
            if uc.roles:
                for r in uc.roles:
                    if r.name not in roles_list:
                        roles_list.append(r.name)
        
        return sorted(roles_list)

    # Permission system methods
    
    def get_permissions(self):
        """Get all permissions for this user from their roles. SysAdmins get all permissions."""
        if self._permission_cache is None:
            permissions = set()
            
            # SysAdmin Override: SysAdmin gets implicit access to EVERYTHING
            if self.is_sysadmin:
                # We can return a special wildcard or just ensure has_permission checks is_sysadmin.
                # But for Flask-Principal which relies on this list, we might want to populate it with ALL permissions.
                # However, filling ALL from DB is expensive.
                # Better strategy: has_permission handles the bypass.
                # But external libs (like flask-principal decorators) might use this list.
                # Let's populate with all defined permissions in the DB if SysAdmin.
                from .permission import Permission
                all_perms = Permission.query.all()
                for p in all_perms:
                    permissions.add(p.name)
            else:
                for role in self.roles:
                    for permission in role.permissions:
                        permissions.add(permission.name)
            
            self._permission_cache = permissions
        return self._permission_cache
    
    def has_permission(self, permission_name):
        """Check if user has a specific permission."""
        # SysAdmin Bypass
        if self.is_sysadmin:
            return True
            
        return permission_name in self.get_permissions()
    
    def has_role(self, role_name):
        """Check if user has a specific role."""
        return any(role.name == role_name for role in self.roles)
    
    @property
    def primary_role(self):
        """Returns the user's highest-level role."""
        from ..club_context import get_current_club_id
        from .user_club import UserClub
        from .role import Role
        from ..auth.permissions import Permissions

        # 1. SysAdmin is global
        if self.is_sysadmin:
             # Find the SysAdmin role object from self.roles or query it
             # Attempt to find in loaded roles first to avoid query
             for r in self.roles:
                 if r.name == Permissions.SYSADMIN:
                     return r
             return Role.query.filter_by(name=Permissions.SYSADMIN).first()

        # 2. Context-aware check
        club_id = get_current_club_id()
        if club_id:
             uc = UserClub.query.filter_by(user_id=self.id, club_id=club_id).first()
             if uc and uc.club_role:
                 return uc.club_role
             return None # Becomes "User" in primary_role_name

        # 3. Fallback (no context)
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
            return uc.contact if uc else None
            
        # Fallback for cases where no club ID is resolved at all: 
        # Return the first available contact this user is associated with.
        # Note: In a multi-club environment, this fallback should be avoided.
        from .user_club import UserClub
        uc = UserClub.query.filter_by(user_id=self.id).first()
        return uc.contact if uc else None

    @property
    def home_club(self):
        """Get the user's home club."""
        from .user_club import UserClub
        uc = UserClub.query.filter_by(user_id=self.id, is_home=True).first()
        return uc.club if uc else None

    def set_home_club(self, club_id):
        """
        Set a specific club as the user's home club.
        Ensures that only one club is marked as home at a time.
        
        Args:
            club_id (int): The ID of the club to set as home. If None, clears home club.
        """
        from .user_club import UserClub
        
        # Reset all clubs for this user to is_home=False
        UserClub.query.filter_by(user_id=self.id).update({'is_home': False})
        
        if club_id:
            # Set the specified club as home
            UserClub.query.filter_by(user_id=self.id, club_id=club_id).update({'is_home': True})
            
        db.session.commit()

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

    @property
    def display_name(self):
        """Returns the contact Name if available, otherwise fallback to username."""
        contact = self.contact
        if contact and contact.Name:
            return contact.Name
        return self.username

    @property
    def full_avatar_url(self):
        """Returns correctly prefixed avatar URL for local assets."""
        if not self.avatar_url:
            return None
        if self.avatar_url.startswith(('http://', 'https://', '/')):
            return self.avatar_url
        return f"/static/{self.avatar_url}"

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

        # 1. Try to find/reuse contact if not linked to this club yet
        if contact is None:
             # Try club-specific first (prioritize existing club members)
             if target_email := email or self.email:
                 contact = Contact.query.join(ContactClub).filter(
                     ContactClub.club_id == club_id,
                     Contact.Email == target_email
                 ).first()
             
             if not contact:
                 contact = Contact.query.join(ContactClub).filter(
                     ContactClub.club_id == club_id,
                     Contact.Name == final_name
                 ).first()

             # Fallback: Check if this user has a contact in ANOTHER club to clone from
             # We DO NOT reuse the ID, but we copy the data to create a new local contact.
             prototype_contact = None
             if not contact:
                 if target_email := email or self.email:
                     prototype_contact = Contact.query.filter_by(Email=target_email).first()
                 if not prototype_contact and final_name:
                     prototype_contact = Contact.query.filter_by(Name=final_name).first()

        # 2. Create if still not found
        if contact is None:
             # Use prototype data if available, otherwise defaults
             source = prototype_contact if prototype_contact else None
             
             contact = Contact(
                 Name=full_name or (source.Name if source else final_name),
                 first_name=first_name or (source.first_name if source else None),
                 last_name=last_name or (source.last_name if source else None),
                 Email=email or self.email or (source.Email if source else None),
                 Phone_Number=phone or self.phone or (source.Phone_Number if source else None),
                 Type='Member',
                 Date_Created=date.today()
             )
             db.session.add(contact)
             db.session.flush()
        else:
             # Sync existing contact
             if full_name: contact.Name = full_name
             if first_name: contact.first_name = first_name
             if last_name: contact.last_name = last_name
             
             # If user doesn't have names, copy from contact
             if not self.first_name and contact.first_name:
                 self.first_name = contact.first_name
             if not self.last_name and contact.last_name:
                 self.last_name = contact.last_name

             if email: contact.Email = email
             if phone: contact.Phone_Number = phone
             
             # Upgrade Guest to Member if they now have a user account
             if contact.Type == 'Guest':
                 contact.Type = 'Member'

        # 3. Ensure UserClub linkage
        if not uc:
             uc = UserClub(
                 user_id=self.id,
                 club_id=club_id,
                 contact_id=contact.id
             )
             db.session.add(uc)
        else:
             uc.contact_id = contact.id
             
        # 4. Ensure ContactClub linkage (for roster/contact management)
        exists = ContactClub.query.filter_by(contact_id=contact.id, club_id=club_id).first()
        if not exists:
            db.session.add(ContactClub(contact_id=contact.id, club_id=club_id))
        
        return contact

    def set_club_role(self, club_id, role_level):
        """
        Set the user's role level for a specific club using UserClub.
        role_level is the bitmask sum of all roles.
        """
        from .user_club import UserClub
        from .club import Club
        from ..club_context import get_current_club_id
        
        if not club_id:
             club_id = get_current_club_id()
             if not club_id:
                 default_club = Club.query.first()
                 club_id = default_club.id if default_club else None
        
        if not club_id:
            return

        existing_uc = UserClub.query.filter_by(user_id=self.id, club_id=club_id).first()
        
        if existing_uc:
            existing_uc.club_role_level = role_level
        else:
            new_uc = UserClub(
                user_id=self.id,
                club_id=club_id,
                club_role_level=role_level
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
