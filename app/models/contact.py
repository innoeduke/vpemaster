"""Contact model for member and guest information."""
from .base import db


class Contact(db.Model):
    __tablename__ = 'Contacts'
    id = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String(100), nullable=False, unique=False)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    Email = db.Column(db.String(120), unique=False, nullable=True)
    Type = db.Column(db.String(50), nullable=False, default='Guest')
    Date_Created = db.Column(db.Date)
    _Completed_Paths = db.Column('Completed_Paths', db.String(255))
    DTM = db.Column(db.Boolean, default=False)
    Phone_Number = db.Column(db.String(50), nullable=True)
    Bio = db.Column(db.Text, nullable=True)
    
    # Migrated from User model
    Member_ID = db.Column(db.String(50), unique=False, nullable=True)
    Mentor_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'), nullable=True)
    _Current_Path = db.Column('Current_Path', db.String(50), nullable=True)
    Next_Project = db.Column(db.String(100), nullable=True)
    credentials = db.Column(db.String(10), nullable=True)
    Avatar_URL = db.Column(db.String(255), nullable=True)
    is_connected = db.Column(db.Boolean, default=True)

    # Contact-level home club. Plain text by design — see
    # docs/CONTACT_USER_CLUB_MODEL.md rule 6. Independent from
    # User.home_club (which drives auth/login/profile). For user-linked
    # contacts, this is backfilled from User.home_club on migration and
    # then drifts independently; for guest contacts, this is the only
    # home club they have.
    home_club = db.Column(db.String(200), nullable=True)

    mentor = db.relationship('Contact', remote_side=[id], foreign_keys=[Mentor_ID], backref='mentees')
    
    # Add cascades for child records to ensure clean deletion of contacts
    waitlists = db.relationship('Waitlist', cascade='all, delete-orphan', back_populates='contact')
    roster_entries = db.relationship('Roster', cascade='all, delete-orphan', back_populates='contact')
    user_club_records = db.relationship('UserClub', cascade='all, delete-orphan', back_populates='contact', foreign_keys='UserClub.contact_id')
    club_memberships = db.relationship('ContactClub', cascade='all, delete-orphan', back_populates='contact')
    registered_paths = db.relationship('ContactPath', cascade='all, delete-orphan', back_populates='contact')
    
    @property
    def Current_Path(self):
        default_path = next((cp for cp in self.registered_paths if cp.is_default), None)
        if not default_path:
            # Fallback: get the first working path
            default_path = next((cp for cp in self.registered_paths if cp.status == 'working'), None)
        if not default_path:
            # Fallback: get the first completed path
            default_path = next((cp for cp in self.registered_paths if cp.status == 'completed'), None)
        
        if default_path and default_path.pathway:
            return default_path.pathway.name
        
        # Final fallback: legacy column value (for cases where Pathway record doesn't exist)
        return self._Current_Path

    @Current_Path.setter
    def Current_Path(self, pathway_name):
        if not pathway_name:
            for cp in self.registered_paths:
                cp.is_default = False
            self._Current_Path = None
            return

        from .project import Pathway
        from .contact_path import ContactPath
        # Find pathway
        pathway = Pathway.query.filter((Pathway.name == pathway_name) | (Pathway.abbr == pathway_name)).first()
        if not pathway:
            self._Current_Path = pathway_name # fallback for compatibility
            return

        # Find if registered
        existing = next((cp for cp in self.registered_paths if cp.path_id == pathway.id), None)
        if existing:
            # Set this as default, unset others
            for cp in self.registered_paths:
                cp.is_default = (cp.id == existing.id)
        else:
            # Create a new working path
            for cp in self.registered_paths:
                cp.is_default = False
            new_cp = ContactPath(contact_id=self.id, path_id=pathway.id, status='working', is_default=True)
            self.registered_paths.append(new_cp)

        self._Current_Path = pathway.name

    @property
    def Completed_Paths(self):
        completed = []
        for cp in self.registered_paths:
            if cp.status == 'completed' and cp.pathway and cp.pathway.abbr:
                completed.append(f"{cp.pathway.abbr}5")
        return "/".join(sorted(completed)) if completed else None

    @Completed_Paths.setter
    def Completed_Paths(self, value):
        self._Completed_Paths = value
        
        if not value:
            # Mark all completed paths as working
            for cp in self.registered_paths:
                if cp.status == 'completed':
                    cp.status = 'working'
            return

        parts = [p.strip() for p in str(value).split('/') if p.strip()]
        from .project import Pathway
        from .contact_path import ContactPath
        import re
        
        specified_pathway_ids = set()
        
        for part in parts:
            # Extract pathway abbreviation (e.g. "PM5" -> "PM")
            match = re.match(r"^([A-Z]+)\d*$", part.upper())
            abbr = match.group(1) if match else part
            
            pathway = Pathway.query.filter((Pathway.abbr == abbr) | (Pathway.name == part)).first()
            if pathway:
                specified_pathway_ids.add(pathway.id)
                # Find if already registered
                cp = next((x for x in self.registered_paths if x.path_id == pathway.id), None)
                if cp:
                    cp.status = 'completed'
                else:
                    new_cp = ContactPath(contact_id=self.id, path_id=pathway.id, status='completed', is_default=False)
                    self.registered_paths.append(new_cp)
                    
        # Any other paths that were completed but not in parts could be set to working
        for cp in self.registered_paths:
            if cp.status == 'completed' and cp.path_id not in specified_pathway_ids:
                cp.status = 'working'

    @property
    def user_id(self):
        """Returns the user_id associated with this contact if any."""
        # 1. Preferred: Find user_id from associated UserClub records
        # Try to match the current club first for context, but return ANY linkage if not found.
        from ..club_context import get_current_club_id
        current_club_id = get_current_club_id()
        
        fallback_uid = None
        for uc in self.user_club_records:
            if uc.user_id:
                if uc.club_id == current_club_id:
                    return uc.user_id
                fallback_uid = uc.user_id
        
        if fallback_uid:
            return fallback_uid

        # 2. Fallback: Match by Email if available
        if self.Email:
            from .user import User
            user = User.query.filter_by(email=self.Email).first()
            if user:
                return user.id
                
        return None

    @property
    def user(self):
        """Get the user associated with this contact if any."""
        # Optimization: Check if batch-populated
        if hasattr(self, '_user'):
            return self._user
            
        uid = self.user_id
        if uid:
            from .user import User
            return User.query.get(uid)
        return None
    
    def update_name_from_parts(self, overwrite=True):
        """Auto-populate Name from first_name and last_name."""
        if (overwrite or not self.Name) and (self.first_name or self.last_name):
            parts = []
            if self.first_name:
                parts.append(self.first_name.strip())
            if self.last_name:
                parts.append(self.last_name.strip())
            self.Name = ' '.join(parts)

    def get_member_pathways(self):
        """
        Get all registered pathways for this contact.
        Returns list of pathway names ordered alphabetically.
        """
        pathways = []
        for cp in self.registered_paths:
            if cp.pathway:
                pathways.append({
                    'name': cp.pathway.name,
                    'status': cp.status,
                    'abbr': cp.pathway.abbr,
                    'path_id': cp.pathway.id
                })
        return sorted(pathways, key=lambda x: x['name'])


    def get_completed_levels(self, pathway_name):
        """
        Get completed level numbers for the given pathway.
        Returns set of integers representing completed levels.
        """
        from .achievement import Achievement
        
        if not pathway_name:
            return set()
        
        # Simple caching on the object
        cache_key = f'_completed_levels_{pathway_name}'
        if hasattr(self, cache_key):
            return getattr(self, cache_key)
        
        uid = self.user_id
        if uid:
            achievements = Achievement.query.filter_by(
                user_id=uid,
                path_name=pathway_name,
                achievement_type='level-completion'
            ).all()
        else:
            achievements = []
        
        res = {a.level for a in achievements if a.level}
        setattr(self, cache_key, res)
        return res
        
    def get_level_achievement_dates(self, pathway_name):
        """
        Get achievement issue dates for the given pathway.
        Returns dict of {level: award_date (str)}.
        """
        from .achievement import Achievement
        
        if not pathway_name:
            return {}
            
        cache_key = f'_level_achievement_dates_{pathway_name}'
        if hasattr(self, cache_key):
            return getattr(self, cache_key)
            
        uid = self.user_id
        if uid:
            achievements = Achievement.query.filter_by(
                user_id=uid,
                path_name=pathway_name,
                achievement_type='level-completion'
            ).all()
        else:
            achievements = []
            
        res = {int(a.level): a.award_date.strftime('%Y-%m-%d') for a in achievements if a.level and a.award_date}
        setattr(self, cache_key, res)
        return res
    
    def get_active_level_at_date(self, pathway_name, reference_date):
        """
        Determines the active level for a given pathway at a specific date.
        
        Logic: The active level is the lowest level N where level N was NOT 
        completed on or before the reference_date.
        
        Args:
            pathway_name: Name of the pathway (e.g., "Dynamic Leadership")
            reference_date: The date to check (datetime.date)
            
        Returns:
            int: The active level (1-5) at that date.
        """
        from .achievement import Achievement
        
        if not pathway_name:
            return 1
            
        # 1. Fetch all level-completion achievements for this pathway
        # Cache them for performance during bulk log processing
        cache_key = f'_achievements_{pathway_name}'
        if not hasattr(self, cache_key):
            uid = self.user_id
            if uid:
                achievements = Achievement.query.filter_by(
                    user_id=uid,
                    path_name=pathway_name,
                    achievement_type='level-completion'
                ).order_by(Achievement.level).all()
                setattr(self, cache_key, achievements)
            else:
                setattr(self, cache_key, [])
        
        achievements = getattr(self, cache_key)
        
        # 2. Find the lowest level that was NOT completed yet on this date
        # Check levels in order
        for level in range(1, 6):
            # Find if this level has a completion record
            comp = next((a for a in achievements if a.level == level), None)
            
            if not comp:
                # Level never completed -> it's the active level
                return level
                
            # Level completed: was it completed AFTER the reference date?
            # If reference_date is on or before award_date, it belongs to this level
            if reference_date <= comp.award_date:
                return level
                
        # If all 5 levels completed on or before reference_date
        return 5
    
    def get_completed_project_ids(self):
        """
        Returns a set of Project IDs that this contact has completed.
        """
        from .session import SessionLog, SessionType, OwnerMeetingRoles
        from .roster import MeetingRole
        from .meeting import Meeting
        
        completed_project_ids = db.session.query(SessionLog.Project_ID)\
            .join(Meeting, SessionLog.meeting_id == Meeting.id)\
            .join(SessionType, SessionLog.Type_ID == SessionType.id)\
            .join(MeetingRole, SessionType.role_id == MeetingRole.id)\
            .filter(
                db.exists().where(
                    db.and_(
                        OwnerMeetingRoles.contact_id == self.id,
                        OwnerMeetingRoles.meeting_id == Meeting.id,
                        OwnerMeetingRoles.role_id == MeetingRole.id,
                        db.or_(
                            OwnerMeetingRoles.session_log_id == SessionLog.id,
                            OwnerMeetingRoles.session_log_id.is_(None)
                        )
                    )
                ),
                Meeting.status == 'finished',
                SessionLog.Project_ID.isnot(None)
            ).all()
        
        return {pid[0] for pid in completed_project_ids}

    def get_available_projects(self):
        """
        Returns a list of Project objects in the contact's current pathway 
        that have not been completed yet.
        """
        projects = self.get_pathway_projects_with_status()
        return [p for p in projects if not p.is_completed]

    def get_pathway_projects_with_status(self):
        """
        Returns a list of Project objects in the contact's current pathway 
        with level, code, and completion status attached.
        """
        if not self.Current_Path:
            return []
            
        from .project import Project, Pathway, PathwayProject
        pathway = Pathway.query.filter((Pathway.name == self.Current_Path) | (Pathway.abbr == self.Current_Path)).first()
        if not pathway:
            return []
            
        # Get all projects in this pathway with level and code
        projects_with_meta = db.session.query(Project, PathwayProject.level, PathwayProject.code, Pathway.abbr)\
            .join(PathwayProject, Project.id == PathwayProject.project_id)\
            .join(Pathway, PathwayProject.path_id == Pathway.id)\
            .filter(PathwayProject.path_id == pathway.id)\
            .order_by(PathwayProject.level, PathwayProject.code)\
            .all()
        
        # Get completed project IDs
        completed_ids = self.get_completed_project_ids()
        
        results = []
        for p, level, code, abbr in projects_with_meta:
            p.level = level
            # Construct standard code: [Abbr][Code]
            p.full_code = f"{abbr}{code}" if abbr else code
            p.is_completed = p.id in completed_ids
            results.append(p)
            
        return results

    def get_primary_club(self):
        """Get the primary club for this contact."""
        # Optimization: Check if batch-populated
        if hasattr(self, '_primary_club'):
            return self._primary_club
            
        from .contact_club import ContactClub
        # Just return the first club found since is_primary is removed
        cc = ContactClub.query.filter_by(contact_id=self.id).first()
        return cc.club if cc else None

    def get_home_club(self):
        """
        Get the home club for this contact.
        Reads from the contact's own `home_club` column directly. This is
        the contact-level home club (display on the contacts page) — it is
        a separate concept from `User.home_club` (which drives auth,
        login, profile, and the current club context). For user-linked
        contacts, both can be set; they drift independently. For guest
        contacts, this is the only home club they have.
        Returns the home club name as a string, or None.
        """
        return self.home_club

    # Removed duplicate user_id and user definitions that were tied strictly to club_context.
    # The properties above handle global identification with club preference.

    @staticmethod
    def populate_users(contacts, club_id=None):
        """
        Batch-populates user records for a list of contacts for a specific club.
        Adds a _user attribute to each contact object to avoid N+1 queries.
        """
        if not contacts:
            return
            
        from .user_club import UserClub
        from ..club_context import get_current_club_id
        
        if not club_id:
            club_id = get_current_club_id()
            
        contact_ids = [c.id for c in contacts]
        ucs = UserClub.query.filter(
            UserClub.contact_id.in_(contact_ids),
            UserClub.club_id == club_id
        ).options(db.joinedload(UserClub.user)).all()
        
        contact_map = {c.id: c for c in contacts}
        user_map = {}
        for uc in ucs:
            if uc.user:
                uc.user._current_user_club = uc
                uc.user._current_contact = contact_map.get(uc.contact_id)
                user_map[uc.contact_id] = uc.user
                
        for contact in contacts:
            contact._user = user_map.get(contact.id)

    @staticmethod
    def populate_primary_clubs(contacts):
        """
        Batch-populates primary club records for a list of contacts.
        Adds a _primary_club attribute to each contact object to avoid N+1 queries.
        """
        if not contacts:
            return
            
        from .contact_club import ContactClub
        contact_ids = [c.id for c in contacts]
        
        # Strategy: Just fetch ONE club for each contact.
        # We can't easily guarantee "which" one without a flag, but for now ANY club is better than none.
        # Ideally, this method should be called populate_clubs and return a list, but for backward compat...
        
        # Optimization: If we are in a club context (which we usually are), we might want THAT club.
        # But this method is static and doesn't know the context unless passed.
        # Let's just fetch all contact clubs for these contacts and pick the first one for each.
        
        ccs = ContactClub.query.filter(
            ContactClub.contact_id.in_(contact_ids)
        ).options(db.joinedload(ContactClub.club)).all()
        
        # Map contact_id -> first available club
        cc_map = {}
        for cc in ccs:
            if cc.contact_id not in cc_map:
                cc_map[cc.contact_id] = cc.club
                
        for contact in contacts:
            contact._primary_club = cc_map.get(contact.id)
    
    def get_club_membership(self, club_id):
        """
        Get membership details for a specific club.
        
        Args:
            club_id: ID of the club
            
        Returns:
            ContactClub object or None
        """
        from .contact_club import ContactClub
        return ContactClub.query.filter_by(contact_id=self.id, club_id=club_id).first()
    
    def get_clubs(self):
        """
        Get all clubs this contact belongs to.
        
        Returns:
            List of Club objects
        """
        from .contact_club import ContactClub
        from .club import Club
        club_ids = [cc.club_id for cc in ContactClub.query.filter_by(contact_id=self.id).all()]
        return Club.query.filter(Club.id.in_(club_ids)).all() if club_ids else []

    @classmethod
    def merge_contacts(cls, primary_id, secondary_ids):
        """
        Merges secondary contacts into primary contact.
        Consolidates related records and deletes secondary contacts.
        """
        from .meeting import Meeting
        from .roster import Roster, Waitlist
        from .session import OwnerMeetingRoles
        from .excomm_officer import ExcommOfficer
        from .contact_club import ContactClub
        from .voting import Vote
        from .achievement import Achievement
        from .user_club import UserClub

        # 1. Handle Junction Table Duplicates first (ContactClub, UserClub)
        # For ContactClub:
        for sid in secondary_ids:
            s_memberships = ContactClub.query.filter_by(contact_id=sid).all()
            for sm in s_memberships:
                # If primary already has a record for this club, delete the secondary's record
                exists = ContactClub.query.filter_by(contact_id=primary_id, club_id=sm.club_id).first()
                if exists:
                    db.session.delete(sm)
                else:
                    # Otherwise move it to primary
                    sm.contact_id = primary_id
        
        # For UserClub:
        secondary_user_ids = set()
        primary_user_id = None
        for uc in UserClub.query.filter_by(contact_id=primary_id).all():
            if uc.user_id:
                primary_user_id = uc.user_id
                break

        for sid in secondary_ids:
            s_uclubs = UserClub.query.filter_by(contact_id=sid).all()
            for suc in s_uclubs:
                if suc.user_id:
                    secondary_user_ids.add(suc.user_id)
                
                # If primary already has a linkage in this club, delete the secondary's record
                # (A contact should generally only be linked to one user per club)
                exists = UserClub.query.filter_by(contact_id=primary_id, club_id=suc.club_id).first()
                if exists:
                    db.session.delete(suc)
                else:
                    suc.contact_id = primary_id

        # 2. Bulk update other related models
        # Roster
        Roster.query.filter(Roster.contact_id.in_(secondary_ids)).update(
            {Roster.contact_id: primary_id}, synchronize_session='fetch'
        )
        # Waitlist
        Waitlist.query.filter(Waitlist.contact_id.in_(secondary_ids)).update(
            {Waitlist.contact_id: primary_id}, synchronize_session='fetch'
        )
        # OwnerMeetingRoles (Session Ownership)
        OwnerMeetingRoles.query.filter(OwnerMeetingRoles.contact_id.in_(secondary_ids)).update(
            {OwnerMeetingRoles.contact_id: primary_id}, synchronize_session='fetch'
        )
        # ExcommOfficer
        ExcommOfficer.query.filter(ExcommOfficer.contact_id.in_(secondary_ids)).update(
            {ExcommOfficer.contact_id: primary_id}, synchronize_session='fetch'
        )
        # Vote
        Vote.query.filter(Vote.contact_id.in_(secondary_ids)).update(
            {Vote.contact_id: primary_id}, synchronize_session='fetch'
        )
        if primary_user_id and secondary_user_ids:
            # We don't need to merge if it's the same user
            secondary_user_ids.discard(primary_user_id)
            if secondary_user_ids:
                Achievement.query.filter(Achievement.user_id.in_(list(secondary_user_ids))).update(
                    {Achievement.user_id: primary_user_id}, synchronize_session='fetch'
                )
        
        # Update Meeting awards and sharing master
        Meeting.query.filter(Meeting.best_table_topic_id.in_(secondary_ids)).update(
            {Meeting.best_table_topic_id: primary_id}, synchronize_session='fetch'
        )
        Meeting.query.filter(Meeting.best_evaluator_id.in_(secondary_ids)).update(
            {Meeting.best_evaluator_id: primary_id}, synchronize_session='fetch'
        )
        Meeting.query.filter(Meeting.best_speaker_id.in_(secondary_ids)).update(
            {Meeting.best_speaker_id: primary_id}, synchronize_session='fetch'
        )
        Meeting.query.filter(Meeting.best_role_taker_id.in_(secondary_ids)).update(
            {Meeting.best_role_taker_id: primary_id}, synchronize_session='fetch'
        )
        Meeting.query.filter(Meeting.sharing_master_id.in_(secondary_ids)).update(
            {Meeting.sharing_master_id: primary_id}, synchronize_session='fetch'
        )
        
        # Update Mentor_ID in Contact table itself (Self-referential)
        cls.query.filter(cls.Mentor_ID.in_(secondary_ids)).update(
            {cls.Mentor_ID: primary_id}, synchronize_session='fetch'
        )

        # 3. Delete secondary contacts
        # Cascade will handle any remaining orphans if missed, but we've updated most.
        cls.query.filter(cls.id.in_(secondary_ids)).delete(synchronize_session=False)

        db.session.commit()

