"""User model for authentication and authorization."""
from flask_login import UserMixin, AnonymousUserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app
from sqlalchemy import event

from .base import db


user_favorite_clubs = db.Table(
    'user_favorite_clubs',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
    db.Column('club_id', db.Integer, db.ForeignKey('clubs.id', ondelete='CASCADE'), primary_key=True)
)


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
    def is_sysadmin(self):
        return self.username == 'sysadmin'
    
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
    favorite_clubs = db.relationship(
        'Club',
        secondary=user_favorite_clubs,
        lazy='dynamic',
        backref=db.backref('favorited_by_users', lazy='dynamic')
    )
    # contact relationship removed, use UserClub.contact instead
    # Actually, lines 71-79 covers roles relationship. first_name lines are 32-45.
    roles = db.relationship(
        'app.models.role.Role',
        secondary='user_clubs',
        lazy='joined',
        primaryjoin='User.id == UserClub.user_id',
        secondaryjoin='UserClub.auth_role_id == app.models.role.Role.id',
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

    def get_verification_token(self, expires_sec=86400):
        s = Serializer(current_app.config['SECRET_KEY'])
        return s.dumps({'verification_user_id': self.id})

    @staticmethod
    def verify_verification_token(token, expires_sec=86400):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, max_age=expires_sec).get('verification_user_id')
        except:
            return None
        return db.session.get(User, user_id)
    
    @property
    def contact_id(self):
        """Standard contact ID for this user (usually from home club)."""
        uc = next((c for c in self.club_memberships if c.is_home), None)
        if not uc and self.club_memberships:
            uc = self.club_memberships[0]
        return uc.contact_id if uc else None
    
    # is_sysadmin logic is in property above

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
            
        return uc.auth_role_id == club_role.id

    def get_roles_for_club(self, club_id):
        """Get all roles for this user in a specific club context."""
        from .user_club import UserClub
        from .role import Role
        from ..auth.permissions import Permissions
        from ..club_context import get_current_club_id
        
        roles_data = []
        
        # Helper to get category for auth roles
        def get_auth_role_category(name):
            if name == Permissions.SYSADMIN: return 'sysadmin'
            if name == Permissions.CLUBADMIN: return 'clubadmin'
            if name == Permissions.OPERATOR: return 'operator'
            if name in (Permissions.STAFF, 'Officer'): return 'staff'
            if name == Permissions.USER: return 'user'
            return 'other'

        # 1. Global SysAdmin check: The 'sysadmin' account is an admin everywhere
        if self.is_sysadmin:
            roles_data.append({
                'id': 0, # Virtual ID for SysAdmin
                'name': 'SysAdmin',
                'type': 'standard',
                'award_category': 'sysadmin'
            })
            
        # 2. Club-specific roles
        # Use cached record if it matches the requested club_id
        if hasattr(self, '_current_user_club') and self._current_user_club and (not club_id or self._current_user_club.club_id == club_id):
            uc = self._current_user_club
        else:
            uc = UserClub.query.filter_by(user_id=self.id, club_id=club_id).first()

        if uc:
            # Aggregate all roles from this membership (bitmask-aware)
            for r in uc.roles:
                if not any(rd['name'] == r.name for rd in roles_data):
                    roles_data.append({
                        'id': r.id,
                        'name': r.name,
                        'type': 'officer' if r.name in (Permissions.CLUBADMIN, Permissions.OPERATOR, Permissions.STAFF) else 'standard',
                        'award_category': get_auth_role_category(r.name)
                    })
            if not uc.roles and not any(rd['name'] == Permissions.USER for rd in roles_data):
                # Fallback if somehow missing
                ur = Role.get_by_name(Permissions.USER)
                if ur:
                    roles_data.append({
                        'id': ur.id,
                        'name': Permissions.USER,
                        'type': 'standard',
                        'award_category': 'user'
                    })
        
        return sorted(roles_data, key=lambda x: x['name'])

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
    
    def has_permission(self, permission_name, club_id=None):
        """Check if user has a specific permission."""
        # SysAdmin Bypass
        if self.is_sysadmin:
            return True
            
        return permission_name in self.get_permissions()

    def has_club_permission(self, permission_name, club_id, **kwargs):
        """
        Check if user has a specific permission within the context of a specific club.
        True if:
        1. User is SysAdmin (global)
        # 2. User has a role in this club that grants the permission
        """
        if self.is_sysadmin:
            return True
            
        # 3. Check for Meeting Manager override
        meeting = kwargs.get('meeting')
        if meeting and meeting.manager_id:
            # If user is the manager of this specific meeting
            user_contact_id = getattr(self, 'contact_id', None)
            if user_contact_id and user_contact_id == meeting.manager_id:
                # Grant Operator-level permissions relevant to meeting management
                if permission_name in {
                    'MEETING_MANAGE', 'BOOKING_OWN', 'VOTING_VIEW_RESULTS', 
                    'VOTING_TRACK_PROGRESS', 'ROSTER_EDIT', 'MEETING_VIEW_PUBLISHED', 'ROSTER_VIEW'
                }:
                    return True
                    
        if not club_id:
            return False
            
        # Get UserClub record for this club
        uc = self.get_user_club(club_id)
        if not uc:
            from .role import Role
            guest_role = Role.get_by_name('Guest')
            if guest_role:
                return guest_role.has_permission(permission_name)
            return False
            
        # Check permissions of all roles assigned in this club (bitmask-aware)
        for r in uc.roles:
            if r.has_permission(permission_name):
                return True
                
        return False
    
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

        # 1. SysAdmin is global account-based
        if self.is_sysadmin:
             return None # Handled in primary_role_name

        # 2. Context-aware check
        club_id = get_current_club_id()
        if club_id:
             uc = UserClub.query.filter_by(user_id=self.id, club_id=club_id).first()
             if uc and uc.club_role:
                 return uc.club_role
             return None # Becomes "Member" in primary_role_name

        # 3. Fallback (no context)
        if not self.roles:
            return None
        return max(self.roles, key=lambda r: r.level if r.level is not None else 0)

    @property
    def primary_role_name(self):
        """Returns the name of the user's highest-level role."""
        if self.is_sysadmin:
            return "SysAdmin"
        role = self.primary_role
        return role.name if role else "Member"

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
        from ..club_context import get_current_club_id
        
        if not club_id:
            club_id = get_current_club_id()
            
        if not club_id:
            return None
            
        # Optimization: Use cached record if available for the current club
        current_club_id = get_current_club_id()
        if club_id == current_club_id and hasattr(self, '_current_user_club'):
            return self._current_user_club
            
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
        from .contact import Contact
        from ..club_context import get_current_club_id
        
        if not club_id:
            club_id = get_current_club_id()
            
        user_ids = [u.id for u in users]
        ucs = UserClub.query.filter(
            UserClub.user_id.in_(user_ids),
            UserClub.club_id == club_id
        ).options(
            db.joinedload(UserClub.contact).joinedload(Contact.mentor)
        ).all()
        
        # Map user_id to UserClub
        uc_map = {uc.user_id: uc for uc in ucs}
        
        # Set transient attributes on users
        for user in users:
            user._current_user_club = uc_map.get(user.id)
            user._current_contact = user._current_user_club.contact if user._current_user_club else None

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
        prototype_contact = None

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
                 Date_Created=date.today(),
                 # Copy additional fields from prototype
                 Member_ID=source.Member_ID if source else None,
                 DTM=source.DTM if source else False,
                 Avatar_URL=source.Avatar_URL if source else None,
                 Current_Path=source.Current_Path if source else None,
                 Bio=source.Bio if source else None,
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
             # Check if this is the first club for the user
             is_first_club = UserClub.query.filter_by(user_id=self.id).count() == 0
             
             uc = UserClub(
                 user_id=self.id,
                 club_id=club_id,
                 contact_id=contact.id,
                 is_home=is_first_club
             )
             db.session.add(uc)
        else:
             uc.contact_id = contact.id
             
        # 4. Ensure ContactClub linkage (for roster/contact management)
        with db.session.no_autoflush:
            exists = ContactClub.query.filter_by(contact_id=contact.id, club_id=club_id).first()
        if not exists:
            db.session.add(ContactClub(contact_id=contact.id, club_id=club_id))
        
        # 5. Recalculate derived metadata (Completed_Paths, credentials, etc.)
        db.session.flush()
        from ..utils import sync_contact_metadata
        sync_contact_metadata(contact.id, commit=False)
        
        return contact

    def set_club_role(self, club_id, role_id_or_level=None, role_id=None, level=None):
        """
        Set the user's role for a specific club using UserClub.
        Accepts role_id (int), level (int), or a positional role_id_or_level.
        """
        from .user_club import UserClub
        from .club import Club
        from .role import Role
        from ..club_context import get_current_club_id
        
        if not club_id:
             club_id = get_current_club_id()
             if not club_id:
                  default_club = Club.query.first()
                  club_id = default_club.id if default_club else None
        
        if not club_id:
            return

        target_role_id = role_id
        target_level = level
        
        # If neither is provided explicitly, try to derive from positional argument
        if role_id_or_level is not None and target_role_id is None and target_level is None:
            all_roles = Role.get_all_cached()
            
            # 1. Try to find a role with this ID exactly (Prefer ID in V2)
            role_by_id = next((r for r in all_roles if r.id == role_id_or_level), None)
            
            # 2. Try to find a role with this Level exactly
            level_match = next((r for r in all_roles if r.level == role_id_or_level), None)
            
            if role_by_id:
                # If we have an ID match, we use it. 
                # (Even if Level match exists, ID is the primary intent in V2 UI/Migration)
                target_role_id = role_by_id.id
                target_level = role_by_id.level
            elif level_match:
                # Fallback to level-based lookup if no ID matches
                target_role_id = level_match.id
                target_level = level_match.level
            else:
                # Fallback to closest level if it looks like a level (heuristic)
                if isinstance(role_id_or_level, int) and role_id_or_level < 100 and all_roles:
                    best_role = min(all_roles, key=lambda r: abs((r.level or 0) - role_id_or_level))
                    target_role_id = best_role.id
                    target_level = role_id_or_level
                else:
                    target_role_id = role_id_or_level # Assume it's an ID that isn't in cache
        
        # If Level was provided explicitly but no ID, fetch the ID
        if target_level is not None and target_role_id is None:
             from .role import Role
             role = Role.query.filter_by(level=target_level).first()
             if role:
                 target_role_id = role.id

        existing_uc = UserClub.query.filter_by(user_id=self.id, club_id=club_id).first()
        
        if existing_uc:
            existing_uc.auth_role_id = target_role_id
        else:
            new_uc = UserClub(
                user_id=self.id,
                club_id=club_id,
                auth_role_id=target_role_id,
            )
            db.session.add(new_uc)

        # Force clear of self-permission cache
        self._permission_cache = None






class AnonymousUser(AnonymousUserMixin):
    """Anonymous user with Guest role permissions."""
    
    _permission_cache = None

    def get_permissions(self):
        """Get permissions for Guest role."""
        # Import here to avoid circular dependencies
        from .role import Role
        
        guest_role = Role.get_by_name('Guest')
        permissions = set()
        if guest_role:
            for permission in guest_role.permissions:
                permissions.add(permission.name)
        
        return permissions

    def has_permission(self, permission_name, club_id=None):
        """Check if guest has a specific permission."""
        return permission_name in self.get_permissions()

    def can(self, permission):
        return self.has_permission(permission)

    @property
    def primary_role_name(self):
        return 'Guest'
