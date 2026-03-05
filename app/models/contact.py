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
    Completed_Paths = db.Column(db.String(255))
    DTM = db.Column(db.Boolean, default=False)
    Phone_Number = db.Column(db.String(50), nullable=True)
    Bio = db.Column(db.Text, nullable=True)
    
    # Migrated from User model
    Member_ID = db.Column(db.String(50), unique=False, nullable=True)
    Mentor_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'), nullable=True)
    Current_Path = db.Column(db.String(50), nullable=True)
    Next_Project = db.Column(db.String(100), nullable=True)
    credentials = db.Column(db.String(10), nullable=True)
    Avatar_URL = db.Column(db.String(255), nullable=True)
    is_connected = db.Column(db.Boolean, default=True)

    mentor = db.relationship('Contact', remote_side=[id], foreign_keys=[Mentor_ID], backref='mentees')
    
    # Add cascades for child records to ensure clean deletion of contacts
    waitlists = db.relationship('Waitlist', cascade='all, delete-orphan', back_populates='contact')
    roster_entries = db.relationship('Roster', cascade='all, delete-orphan', back_populates='contact')
    user_club_records = db.relationship('UserClub', cascade='all, delete-orphan', back_populates='contact', foreign_keys='UserClub.contact_id')
    club_memberships = db.relationship('ContactClub', cascade='all, delete-orphan', back_populates='contact')
    
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
        Get distinct pathways for this contact from their session logs.
        Returns list of pathway names ordered alphabetically.
        """
        from sqlalchemy import distinct, union
        from .session import SessionLog, SessionType, OwnerMeetingRoles
        from .meeting import Meeting
        from .roster import MeetingRole
        from .achievement import Achievement
        
        # 1. Get pathways from SessionLog (ONLY if Project_ID is set = Real Progress)
        q_logs = db.session.query(SessionLog.pathway)\
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
                SessionLog.pathway.isnot(None),
                SessionLog.pathway != '',
                SessionLog.Project_ID.isnot(None) # <--- CRITICAL FIX: Only real projects count
            ).distinct()
            
        # 2. Get pathways from Achievements (Completed Levels/Paths)
        uid = self.user_id
        if uid:
            q_ach = db.session.query(Achievement.path_name)\
                .filter(
                    Achievement.user_id == uid,
                    Achievement.path_name.isnot(None),
                    Achievement.path_name != ''
                ).distinct()
        else:
            q_ach = db.session.query(Achievement.path_name).filter(db.literal_column('0 = 1'))  # No results
            
        # 3. Union results
        final_query = q_logs.union(q_ach)
        
        results = [r[0] for r in final_query.all()]
        results.sort()
        return results


    def get_completed_levels(self, pathway_name):
        """
        Get completed level numbers for the given pathway.
        Returns set of integers representing completed levels.
        """
        from .achievement import Achievement
        
        if not pathway_name:
            return set()
        
        uid = self.user_id
        if uid:
            achievements = Achievement.query.filter_by(
                user_id=uid,
                path_name=pathway_name,
                achievement_type='level-completion'
            ).all()
        else:
            achievements = []
        
        return {a.level for a in achievements if a.level}
    
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
        Looks up UserClub by User matched via Member_ID where is_home = True.
        """
        if getattr(self, '_home_club_checked', False):
            return getattr(self, '_home_club', None)
            
        from .user_club import UserClub
        from .user import User
        
        self._home_club_checked = True
        self._home_club = None
        
        if not self.Member_ID:
            return None
            
        # 1. Find the User associated with this Member_ID
        user = User.query.filter_by(member_no=self.Member_ID).first()
        if not user:
             return None
             
        # 2. Find their home club via UserClub
        home_uc = UserClub.query.filter_by(user_id=user.id, is_home=True).first()
        if home_uc:
            self._home_club = home_uc.club
            
        return self._home_club

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
        
        user_map = {uc.contact_id: uc.user for uc in ucs}
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
        
        # Update Meeting awards and manager
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
        Meeting.query.filter(Meeting.manager_id.in_(secondary_ids)).update(
            {Meeting.manager_id: primary_id}, synchronize_session='fetch'
        )
        
        # Update Mentor_ID in Contact table itself (Self-referential)
        cls.query.filter(cls.Mentor_ID.in_(secondary_ids)).update(
            {cls.Mentor_ID: primary_id}, synchronize_session='fetch'
        )

        # 3. Delete secondary contacts
        # Cascade will handle any remaining orphans if missed, but we've updated most.
        cls.query.filter(cls.id.in_(secondary_ids)).delete(synchronize_session=False)

        db.session.commit()

