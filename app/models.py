from . import db
from .constants import ProjectID
from sqlalchemy import func
from sqlalchemy.orm import joinedload, subqueryload


class Contact(db.Model):
    __tablename__ = 'Contacts'
    id = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String(100), nullable=False, unique=True)
    Email = db.Column(db.String(120), unique=True, nullable=True)
    Type = db.Column(db.String(50), nullable=False, default='Guest')
    Club = db.Column(db.String(100))
    Date_Created = db.Column(db.Date)
    Completed_Paths = db.Column(db.String(255))
    DTM = db.Column(db.Boolean, default=False)
    Phone_Number = db.Column(db.String(50), nullable=True)
    Bio = db.Column(db.Text, nullable=True)
    
    # Migrated from User model
    Member_ID = db.Column(db.String(50), unique=True, nullable=True)
    Mentor_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'), nullable=True)
    Current_Path = db.Column(db.String(50), nullable=True)
    Next_Project = db.Column(db.String(100), nullable=True)
    credentials = db.Column(db.String(10), nullable=True)
    Avatar_URL = db.Column(db.String(255), nullable=True)

    mentor = db.relationship('Contact', remote_side=[id], foreign_keys=[Mentor_ID], backref='mentees')

    def get_member_pathways(self):
        """
        Get distinct pathways for this contact from their session logs.
        Returns list of pathway names ordered alphabetically.
        """
        from sqlalchemy import distinct
        query = db.session.query(SessionLog.pathway).filter(
            SessionLog.Owner_ID == self.id,
            SessionLog.pathway.isnot(None),
            SessionLog.pathway != ''
        ).distinct().order_by(SessionLog.pathway)
        return [r[0] for r in query.all()]

    def get_completed_levels(self, pathway_name):
        """
        Get completed level numbers for the given pathway.
        Returns set of integers representing completed levels.
        """
        if not pathway_name:
            return set()
        
        achievements = Achievement.query.filter_by(
            contact_id=self.id,
            path_name=pathway_name,
            achievement_type='level-completion'
        ).all()
        return {a.level for a in achievements if a.level}


from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from . import login_manager
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask import current_app

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

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
        from .auth.utils import ROLE_PERMISSIONS 
        
        # If user role is None, treat as Guest
        role = self.Role if self.Role else "Guest"
        return permission in ROLE_PERMISSIONS.get(role, set())

    @property
    def is_admin(self):
        return self.Role == 'Admin'

    @property
    def is_officer(self):
        return self.Role in ['Officer', 'Admin', 'VPE']


class Project(db.Model):
    __tablename__ = 'Projects'
    id = db.Column(db.Integer, primary_key=True)
    Project_Name = db.Column(db.String(255), nullable=False)
    Format = db.Column(db.String(50))
    Duration_Min = db.Column(db.Integer)
    Duration_Max = db.Column(db.Integer)
    Introduction = db.Column(db.String(1000))
    Overview = db.Column(db.String(1000))
    Purpose = db.Column(db.String(255))
    Requirements = db.Column(db.String(500))
    Resources = db.Column(db.String(500))
    
    @property
    def is_generic(self):
        """Returns True if this is the generic project."""
        return self.id == ProjectID.GENERIC

    @property
    def is_presentation(self):
        """Returns True if this is a presentation project."""
        return self.Format == 'Presentation'

    @property
    def is_prepared_speech(self):
        """Returns True if this is a prepared speech project."""
        return self.Format == 'Prepared Speech'

    def resolve_context(self, context_path_name=None):
        """
        Helper to find the best matching PathwayProject entry and its Pathway.
        Returns tuple (PathwayProject, Pathway).
        """
        pp = None
        path_obj = None
        
        if context_path_name:
        # Try finding by name first, then by abbreviation
            path_obj = db.session.query(Pathway).filter(
                (Pathway.name == context_path_name) | (Pathway.abbr == context_path_name)
            ).first()
        
            if path_obj:
                pp = db.session.query(PathwayProject).filter_by(
                    path_id=path_obj.id, project_id=self.id).first()
                if not pp:
                    path_obj = None # Reset if project not found in this path

        # Fallback: Check if it belongs to ANY pathway
        if not pp:
            pp = db.session.query(PathwayProject).filter_by(project_id=self.id).first()
            if pp:
                path_obj = db.session.get(Pathway, pp.path_id)
        
        return pp, path_obj
    
    @classmethod
    def prefetch_context(cls, project_ids):
        """
        Pre-fetch PathwayProject data for a list of project IDs to avoid N+1 queries.
        Returns a cache dictionary: {project_id: [{'pp': PathwayProject, 'path': Pathway}, ...]}
        """
        if not project_ids:
            return {}

        pp_entries = db.session.query(PathwayProject, Pathway)\
            .join(Pathway, PathwayProject.path_id == Pathway.id)\
            .filter(PathwayProject.project_id.in_(project_ids))\
            .all()
            
        pp_cache = {}
        for pp, path in pp_entries:
            if pp.project_id not in pp_cache:
                pp_cache[pp.project_id] = []
            pp_cache[pp.project_id].append({'pp': pp, 'path': path})
        return pp_cache

    @classmethod
    def resolve_context_from_cache(cls, project_id, context_path_name, cache):
        """
        Resolve context (PathwayProject, Pathway) using the pre-fetched cache.
        """
        if not project_id or project_id not in cache:
            return None, None
            
        entries = cache[project_id]
        match = None
        
        # 1. Try exact match by name or abbr
        if context_path_name:
            for entry in entries:
                if entry['path'].name == context_path_name or entry['path'].abbr == context_path_name:
                    match = entry
                    break
        
        # 2. Fallback: Take first available if no match found
        if not match and entries:
            match = entries[0]
            
        if match:
            return match['pp'], match['path']
        return None, None

    def get_code(self, context_path_name=None):
        """
        Returns the project code based on a pathway context.
        """
        # Handle generic project
        if self.is_generic:
            return "TM1.0"

        if self.is_presentation:
            context_path_name = None

        pp, path_obj = self.resolve_context(context_path_name)

        if pp:
            if path_obj and path_obj.abbr:
                return f"{path_obj.abbr}{pp.code}"
            else:
                return pp.code

        return ""

    def get_level(self, context_path_name=None):
        """
        Returns the level based on a pathway context.
        """
        if self.is_generic:
            return 1
            
        if self.is_presentation:
            context_path_name = None
            
        pp, _ = self.resolve_context(context_path_name)
        if pp and pp.level:
            return pp.level
            
        return 1


class Meeting(db.Model):
    __tablename__ = 'Meetings'
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(255), default='Keynote Speech')
    Meeting_Number = db.Column(db.SmallInteger, unique=True, nullable=False)
    Meeting_Date = db.Column(db.Date)
    Meeting_Title = db.Column(db.String(255))
    Subtitle = db.Column(db.String(255), nullable=True)
    Start_Time = db.Column(db.Time)
    Meeting_Template = db.Column(db.String(100))
    WOD = db.Column(db.String(100))
    best_table_topic_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    best_evaluator_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    best_speaker_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    best_role_taker_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    media_id = db.Column(db.Integer, db.ForeignKey('Media.id', use_alter=True))
    ge_mode = db.Column(db.Integer, default=0)
    status = db.Column(db.Enum('unpublished', 'not started', 'running', 'finished', 'cancelled', name='meeting_status'),
                       default='unpublished', nullable=False)
    nps = db.Column(db.Float, nullable=True)
    manager_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'))

    manager = db.relationship('Contact', foreign_keys=[manager_id], backref='managed_meetings')

    best_table_topic_speaker = db.relationship(
        'Contact', foreign_keys=[best_table_topic_id])
    best_evaluator = db.relationship(
        'Contact', foreign_keys=[best_evaluator_id])
    best_speaker = db.relationship('Contact', foreign_keys=[best_speaker_id])
    best_role_taker = db.relationship(
        'Contact', foreign_keys=[best_role_taker_id])
    media = db.relationship('Media', foreign_keys=[media_id])

    def get_best_award_ids(self):
        """
        Gets the set of best award IDs for this meeting.
        
        Returns:
            set: Set of award IDs
        """
        return {
            award_id for award_id in [
                self.best_table_topic_id,
                self.best_evaluator_id,
                self.best_speaker_id,
                self.best_role_taker_id
            ] if award_id
        }

    def delete_full(self):
        """
        Deletes the meeting and all associated data in the correct order.
        Returns:
            tuple: (success (bool), message (str or None))
        """
        try:
            # 1. Delete Waitlist entries
            Waitlist.delete_for_meeting(self.Meeting_Number)

            # 2. Delete SessionLog entries
            SessionLog.delete_for_meeting(self.Meeting_Number)

            # 3. Delete Roster and RosterRole entries
            Roster.delete_for_meeting(self.Meeting_Number)

            # 4. Delete Vote entries
            Vote.delete_for_meeting(self.Meeting_Number)

            # 5. Handle Meeting's Media
            if self.media_id:
                media_to_delete = self.media
                self.media_id = None # Break the link first
                db.session.delete(media_to_delete)

            # 6. Delete the Meeting itself
            db.session.delete(self)
            
            db.session.commit()
            return True, None
            
        except Exception as e:
            db.session.rollback()
            return False, str(e)


class SessionType(db.Model):
    __tablename__ = 'Session_Types'
    id = db.Column(db.Integer, primary_key=True)
    Title = db.Column(db.String(255), nullable=False, unique=True)
    Default_Owner = db.Column(db.String(255))
    Is_Section = db.Column(db.Boolean, default=False)
    Is_Hidden = db.Column(db.Boolean, default=False)
    Predefined = db.Column(db.Boolean, default=True)
    Valid_for_Project = db.Column(db.Boolean, default=False)
    Duration_Min = db.Column(db.Integer)
    Duration_Max = db.Column(db.Integer)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=True)

    role = db.relationship('Role', backref='session_types')


class SessionLog(db.Model):
    __tablename__ = 'Session_Logs'
    id = db.Column(db.Integer, primary_key=True)
    Meeting_Number = db.Column(db.SmallInteger, db.ForeignKey(
        'Meetings.Meeting_Number'), nullable=False)
    Meeting_Seq = db.Column(db.Integer)
    # For custom titles like speeches
    Session_Title = db.Column(db.String(255))
    Type_ID = db.Column(db.Integer, db.ForeignKey(
        'Session_Types.id'), nullable=False)
    Owner_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    credentials = db.Column(db.String(255), default='')
    Project_ID = db.Column(db.Integer, db.ForeignKey('Projects.id'))
    Start_Time = db.Column(db.Time)
    Duration_Min = db.Column(db.Integer, default=0)
    Duration_Max = db.Column(db.Integer)
    Notes = db.Column(db.String(1000))
    Status = db.Column(db.String(50))
    state = db.Column(db.String(50), nullable=False,
                      default='active')  # Can be 'active', 'waiting', 'cancelled'
    project_code = db.Column(db.String(10))
    pathway = db.Column(db.String(100))

    meeting = db.relationship('Meeting', backref='session_logs')
    project = db.relationship('Project', backref='session_logs')
    owner = db.relationship('Contact', backref='session_logs')
    session_type = db.relationship('SessionType', backref='session_logs')

    media = db.relationship('Media', backref='session_log',
                            uselist=False, cascade='all, delete-orphan')

    def derive_project_code(self, owner_contact=None):
        """
        Derives the 'project_code' based on the role, project, and owner's pathway.
        Consolidated logic from legacy utils.derive_project_code.
        """
        import re
        from .utils import get_project_code
        
        contact = owner_contact or self.owner
        if not contact or not contact.Current_Path:
            return None

        pathway_name = contact.Current_Path
        path_obj = db.session.query(Pathway).filter_by(name=pathway_name).first()
        if not path_obj:
            return None

        pathway_suffix = path_obj.abbr
        role_name = self.session_type.role.name if self.session_type and self.session_type.role else None

        # --- Priority 1: Speaker/Evaluator with Project ID ---
        # Dynamically identify roles linked to session types valid for projects
        project_specific_roles = [st.role.name for st in SessionType.query.filter_by(Valid_for_Project=True).all() if st.role]
        
        is_presentation = (self.session_type and self.session_type.Title == 'Presentation')
        
        if (role_name in project_specific_roles or is_presentation) and self.Project_ID:
            # For presentations, we might want to use self.pathway if it's explicitly set to a series
            # but per requirement, we use owner's current path for the DB field, 
            # while Project.get_code will naturally find the series fallback.
            code = get_project_code(self.Project_ID, pathway_name)
            if code:
                return code

        # --- Priority 2: Other roles - Use highest level achievement + 1 ---
        else:
            # Determine base level from contact.credentials for consistency
            start_level = 1
            if contact.credentials:
                # Match the current path abbreviation followed by a level number
                match = re.match(rf"^{pathway_suffix}(\d+)$", contact.credentials.strip().upper())
                if match:
                    level_achieved = int(match.group(1))
                    # If level L is completed, the current work is for level L+1 (capped at 5)
                    start_level = min(level_achieved + 1, 5)
                
            return f"{pathway_suffix}{start_level}"

        return None

    def get_display_level_and_type(self, pathway_cache=None):
        """
        Determine log type, display level, and project code for this session log.
        
        Args:
            pathway_cache (dict, optional): Pre-fetched pathway/project data for performance.
                                            Format: {project_id: {pathway_id: PathwayProject}}
        
        Returns:
            tuple: (display_level, log_type, project_code)
                   - display_level: str (e.g., "1", "2", "General")
                   - log_type: str ("speech" or "role")
                   - project_code: str (e.g., "SR1.1", "EH2.3", or "")
        """
        import re
        
        display_level = "General"
        log_type = 'role'
        project_code = ""
        
        if not self.session_type or not self.session_type.role:
            return display_level, log_type, project_code
        
        is_prepared_speech = self.project and self.project.is_prepared_speech
        
        # Determine if this is a speech
        if (self.session_type.Valid_for_Project and self.Project_ID and self.Project_ID != ProjectID.GENERIC) or is_prepared_speech:
            log_type = 'speech'
            pathway_abbr = None
            found_data = False
            
            # Priority 1: Lookup PathwayProject data (Canonical)
            if self.Project_ID:
                found_via_cache = False
                if pathway_cache and self.Project_ID in pathway_cache:
                    # Use cached data if available
                    pp_data = pathway_cache[self.Project_ID]
                    if pp_data:
                        # Find the BEST PathwayProject matching the user's context
                        target_path = self.pathway or (self.owner.Current_Path if self.owner else None)
                        first_pp = None
                        
                        if target_path:
                            for pp in pp_data.values():
                                if pp.pathway and pp.pathway.name == target_path:
                                    first_pp = pp
                                    break
                        
                        # Fallback to any if not found
                        if not first_pp:
                             first_pp = next(iter(pp_data.values()))

                        display_level = str(first_pp.level) if first_pp.level else "1"
                        # Optimized: Use pre-loaded relationship from cache
                        if first_pp.pathway and first_pp.pathway.abbr:
                            pathway_abbr = first_pp.pathway.abbr
                        
                        # Set project code from canonical source immediately
                        if pathway_abbr:
                             project_code = f"{pathway_abbr}{first_pp.code}"
                        else:
                             project_code = first_pp.code
                        
                        found_via_cache = True
                        found_data = True
                
                if not found_via_cache:
                    # No cache, query directly
                    # Try to find match with log's own pathway first, then user's current path
                    target_path_name = self.pathway or (self.owner.Current_Path if self.owner else None)
                    
                    if target_path_name:
                        target_path = Pathway.query.filter_by(name=target_path_name).first()
                        if target_path:
                            pp = PathwayProject.query.filter_by(
                                project_id=self.Project_ID, 
                                path_id=target_path.id
                            ).first()
                            if pp:
                                pathway_abbr = target_path.abbr
                                display_level = str(pp.level) if pp.level else "1"
                                project_code = f"{pathway_abbr}{pp.code}" if pathway_abbr else pp.code
                                found_data = True
                        
                    # Fallback: any pathway
                    if not found_data:
                        pp = PathwayProject.query.filter_by(project_id=self.Project_ID).first()
                        if pp:
                            path_obj = db.session.get(Pathway, pp.path_id)
                            if path_obj:
                                pathway_abbr = path_obj.abbr
                                display_level = str(pp.level) if pp.level else "1"
                                project_code = f"{pathway_abbr}{pp.code}"
                                found_data = True

            # Priority 2: Use project_code if no canonical data found (or as supplement?)
            # Actually, if we found data, we trust DB. If not, use snapshot.
            if not found_data and self.project_code:
                match = re.match(r"([A-Z]+)(\d+)", self.project_code)
                if match:
                    pathway_abbr = match.group(1)
                    display_level = str(match.group(2))
                    project_code = self.project_code
        
        else:  # It's a role
            if self.project_code:
                match = re.match(r"([A-Z]+)(\d+)", self.project_code)
                if match:
                    display_level = str(match.group(2))
        
        return display_level, log_type, project_code
    

    
    def update_media(self, url):
        """Update, create, or delete associated media."""
        if url:
            if self.media:
                self.media.url = url
            else:
                from .models import Media
                self.media = Media(url=url)
        elif self.media:
            db.session.delete(self.media)

    def update_pathway(self, pathway_name):
        """
        Update log pathway and sync with user profile.
        CRITICAL RULE: Only 'pathway'-type paths (e.g., "Presentation Mastery") are stored in 
        SessionLog.pathway and Contact.Current_Path. 'presentation'-type paths (Series) 
        are used purely for project lookup and should NEVER be saved here.
        """
        if not pathway_name:
            return
            
        # Verify the pathway type in the database
        path_obj = Pathway.query.filter_by(name=pathway_name).first()
        if not path_obj or path_obj.type != 'pathway':
            # Do not allow storing series/presentation-type paths in the main pathway column
            return

        old_pathway = self.pathway
        self.pathway = pathway_name
        
        # Sync to user profile if relevant
        if self.owner and old_pathway != pathway_name:
            # Sync to the Contact's current path (ensures profile is updated)
            self.owner.Current_Path = pathway_name
            db.session.add(self.owner)

    def update_durations(self, data, updated_project=None):
        """
        Update durations based on structural changes.
        Priority: Project Defaults > Session Type Defaults > Preserve Manual Edits.
        """
        from .models import SessionType
        
        new_project_id = data.get('project_id')
        if new_project_id in [None, "", "null"]:
            new_project_id = None
        else:
            try:
                new_project_id = int(new_project_id)
            except (ValueError, TypeError):
                new_project_id = None

        project_changed = (self.Project_ID != new_project_id)
        
        new_st_title = data.get('session_type_title')
        st_changed = (new_st_title and self.session_type and self.session_type.Title != new_st_title)

        # Update Project ID first if provided
        if 'project_id' in data:
            self.Project_ID = new_project_id

        if project_changed and self.Project_ID:
            if updated_project:
                self.Duration_Min = updated_project.Duration_Min
                self.Duration_Max = updated_project.Duration_Max
        elif st_changed:
            new_st = SessionType.query.filter_by(Title=new_st_title).first()
            if new_st:
                self.Duration_Min = new_st.Duration_Min
                self.Duration_Max = new_st.Duration_Max

    def get_summary_data(self):
        """Get project name, code, and pathway for response serialization."""
        from .models import Project
        
        project_name = "N/A"
        project_code = ""
        current_pathway = self.pathway or (self.owner.Current_Path if self.owner else "N/A")

        if self.Project_ID:
            project = db.session.get(Project, self.Project_ID)
            if project:
                project_name = project.Project_Name
                
                # Use the more robust logic to get level, type, and code
                _, _, derived_code = self.get_display_level_and_type()
                project_code = derived_code

        return {
            "project_name": project_name,
            "project_code": project_code,
            "pathway": current_pathway
        }

    def matches_filters(self, pathway=None, level=None, status=None, log_type=None):
        """
        Check if this log matches the given filters.
        
        Args:
            pathway (str, optional): Pathway name to filter by (or 'all' for no filtering)
            level (str, optional): Level to filter by (e.g., "1", "2")
            status (str, optional): Status to filter by (e.g., "Completed")
            log_type (str, optional): Pre-determined log type ("speech" or "role")
        
        Returns:
            bool: True if log matches all provided filters
        """
        # Level filter
        if level and hasattr(self, '_display_level'):
            if self._display_level != level:
                return False
        
        # Pathway filter (only for speeches or if pathway is explicitly set)
        if pathway and pathway != 'all':
            current_log_path = getattr(self, 'pathway', None)
            
            # If log has a pathway and it doesn't match → reject
            if current_log_path and current_log_path != pathway:
                return False
            
            # If log has no pathway:
            # - Speeches must belong to the selected pathway → reject
            # - Roles are generic → accept
            if not current_log_path and log_type == 'speech':
                return False
        
        # Status filter
        if status:
            if log_type == 'speech':
                if self.Status != status:
                    return False
            else:  # role
                # For roles, only show if linked to project AND status matches
                if not (self.Project_ID and self.Status == status):
                    return False
        
        return True

    @classmethod
    def assign_role_owner(cls, target_log, new_owner_id):
        """
        Assigns an owner to a session log (and related logs if role is not distinct).
        Updates credentials and project codes.
        Syncs with Roster.
        
        Args:
            target_log: The SessionLog object to update (or one of them)
            new_owner_id: ID of the new owner (or None to unassign)
            
        Returns:
            list: List of updated SessionLog objects
        """
        from .models import SessionType, Role, Contact, Pathway, PathwayProject, Roster, Project
        from .utils import derive_credentials
        from .constants import SessionTypeID
        
        # 1. Identify all logs to update (handle is_distinct)
        session_type = target_log.session_type
        role_obj = session_type.role if session_type else None
        
        sessions_to_update = [target_log]
        
        if role_obj and not role_obj.is_distinct:
            # Find all logs for this role in this meeting
            target_role_id = role_obj.id
            current_owner_id = target_log.Owner_ID
            
            query = db.session.query(cls)\
                .join(SessionType, cls.Type_ID == SessionType.id)\
                .join(Role, SessionType.role_id == Role.id)\
                .filter(cls.Meeting_Number == target_log.Meeting_Number)\
                .filter(Role.id == target_role_id)
            
            if current_owner_id is None:
                query = query.filter(cls.Owner_ID.is_(None))
            else:
                query = query.filter(cls.Owner_ID == current_owner_id)
                
            sessions_to_update = query.all()

        # 2. Prepare Data (Credentials, Project Code)
        owner_contact = db.session.get(Contact, new_owner_id) if new_owner_id else None
        new_credentials = derive_credentials(owner_contact)
        
        # Capture original owner from the target log (assuming others are consistent)
        original_owner_id = target_log.Owner_ID

        # 3. Update Logs
        for log in sessions_to_update:
            log.Owner_ID = new_owner_id
            log.credentials = new_credentials
            
            # Project Code Logic
            new_path_level = None
            if owner_contact:
                # Basic derivation
                new_path_level = log.derive_project_code(owner_contact)
                
                # Auto-Resolution from Next_Project for Prepared Speeches
                # This logic checks if the planned Next_Project matches strict criteria
                if owner_contact.Next_Project and log.Type_ID == SessionTypeID.PREPARED_SPEECH:
                    current_path_name = owner_contact.Current_Path
                    if current_path_name:
                        pathway = Pathway.query.filter_by(name=current_path_name).first()
                        if pathway and pathway.abbr:
                            if owner_contact.Next_Project.startswith(pathway.abbr):
                                code_suffix = owner_contact.Next_Project[len(pathway.abbr):]
                                pp = PathwayProject.query.filter_by(
                                    path_id=pathway.id,
                                    code=code_suffix
                                ).first()
                                if pp:
                                    log.Project_ID = pp.project_id
                                    new_path_level = owner_contact.Next_Project
            
            log.project_code = new_path_level

        # 4. Sync Roster
        if role_obj:
            # Handle unassign old
            if original_owner_id and original_owner_id != new_owner_id:
                Roster.sync_role_assignment(target_log.Meeting_Number, original_owner_id, role_obj, 'unassign')
            
            # Handle assign new
            if new_owner_id:
                Roster.sync_role_assignment(target_log.Meeting_Number, new_owner_id, role_obj, 'assign')

        return sessions_to_update

    @classmethod
    def fetch_for_meeting(cls, selected_meeting_number, meeting_obj=None):
        """
        Fetches session logs for a given meeting, filtering by user role access where appropriate.
        
        Args:
            selected_meeting_number: Meeting number to fetch logs for
            meeting_obj: Optional meeting object for authorization check
        
        Returns:
            list: Session logs with eager-loaded relationships
        """
        from .auth.utils import is_authorized
        
        query = db.session.query(cls)\
            .options(
                joinedload(cls.session_type).joinedload(SessionType.role),
                joinedload(cls.owner),
                subqueryload(cls.waitlists).joinedload(Waitlist.contact)
            )\
            .join(SessionType, cls.Type_ID == SessionType.id)\
            .join(Role, SessionType.role_id == Role.id)\
            .filter(cls.Meeting_Number == selected_meeting_number)\
            .filter(Role.name != '', Role.name.isnot(None))

        if not is_authorized('BOOKING_ASSIGN_ALL', meeting=meeting_obj):
            query = query.filter(Role.type != 'officer')

        return query.all()

    @classmethod
    def delete_for_meeting(cls, meeting_number):
        """Deletes all session logs for a specific meeting."""
        logs = cls.query.filter_by(Meeting_Number=meeting_number).all()
        for log in logs:
            if log.media:
                db.session.delete(log.media)
            db.session.delete(log)


class LevelRole(db.Model):
    __tablename__ = 'level_roles'
    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.Integer, nullable=False)
    role = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    count_required = db.Column(db.Integer, nullable=False, default=0)


class Pathway(db.Model):
    __tablename__ = 'pathways'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    abbr = db.Column(db.String(5))
    type = db.Column(db.String(20))
    status = db.Column(db.Enum('active', 'inactive', 'obsolete', name='pathway_status_enum'), default='active', nullable=False)


class PathwayProject(db.Model):
    __tablename__ = 'pathway_projects'
    id = db.Column(db.Integer, primary_key=True)
    path_id = db.Column(db.Integer, db.ForeignKey('pathways.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('Projects.id'))
    code = db.Column(db.String(10))
    level = db.Column(db.Integer, nullable=True)
    type = db.Column(db.Enum('elective', 'required', 'other', name='pathway_project_type_enum'), nullable=False)

    pathway = db.relationship('Pathway', backref='pathway_projects')


class Media(db.Model):
    __tablename__ = 'Media'
    id = db.Column(db.Integer, primary_key=True)
    log_id = db.Column(db.Integer, db.ForeignKey(
        'Session_Logs.id', ondelete='SET NULL'), nullable=True)
    url = db.Column(db.String(1024), nullable=True)
    notes = db.Column(db.Text, nullable=True)


class Waitlist(db.Model):
    __tablename__ = 'waitlists'
    id = db.Column(db.Integer, primary_key=True)
    session_log_id = db.Column(db.Integer, db.ForeignKey(
        'Session_Logs.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey(
        'Contacts.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=True)

    session_log = db.relationship('SessionLog', backref='waitlists')
    contact = db.relationship('Contact', backref='waitlists')

    @classmethod
    def delete_for_meeting(cls, meeting_number):
        """Deletes all waitlist entries associated with a meeting."""
        # Find session logs for the meeting to identify relevant waitlists
        session_logs = SessionLog.query.filter_by(Meeting_Number=meeting_number).all()
        session_log_ids = [log.id for log in session_logs]
        
        if session_log_ids:
            cls.query.filter(cls.session_log_id.in_(session_log_ids)).delete(synchronize_session=False)


class RosterRole(db.Model):
    """Junction table for many-to-many relationship between Roster and Role"""
    __tablename__ = 'roster_roles'
    id = db.Column(db.Integer, primary_key=True)
    roster_id = db.Column(db.Integer, db.ForeignKey('roster.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    
    # Unique constraint to prevent duplicate role assignments
    __table_args__ = (
        db.UniqueConstraint('roster_id', 'role_id', name='uq_roster_role'),
    )


class Roster(db.Model):
    __tablename__ = 'roster'
    id = db.Column(db.Integer, primary_key=True)
    meeting_number = db.Column(db.Integer, nullable=False)
    order_number = db.Column(db.Integer, nullable=True)
    ticket = db.Column(db.String(20), nullable=True)
    contact_id = db.Column(db.Integer, db.ForeignKey(
        'Contacts.id'), nullable=True)
    contact_type = db.Column(db.String(50), nullable=True)

    contact = db.relationship('Contact', backref='roster_entries')
    roles = db.relationship('Role', secondary='roster_roles', backref='roster_entries')

    def add_role(self, role):
        """Add a role to this roster entry if not already assigned"""
        if not self.has_role(role):
            self.roles.append(role)
            return True
        return False

    def remove_role(self, role):
        """Remove a role from this roster entry if assigned"""
        if self.has_role(role):
            self.roles.remove(role)
            return True
        return False

    def has_role(self, role):
        """Check if this roster entry has the specified role"""
        return role in self.roles

    def clear_roles(self):
        """Remove all roles from this roster entry"""
        self.roles = []

    def get_role_names(self):
        """Get list of role names for this roster entry"""
        return [role.name for role in self.roles]

    @classmethod
    def delete_for_meeting(cls, meeting_number):
        """Deletes all roster entries and associated roles for a meeting."""
        rosters = cls.query.filter_by(meeting_number=meeting_number).all()
        roster_ids = [r.id for r in rosters]
        
        if roster_ids:
            # Delete assignments first
            RosterRole.query.filter(RosterRole.roster_id.in_(roster_ids)).delete(synchronize_session=False)
            # Delete roster entries
            cls.query.filter(cls.id.in_(roster_ids)).delete(synchronize_session=False)

    @staticmethod
    def sync_role_assignment(meeting_number, contact_id, role_obj, action):
        """
        Sync roster role assignments when booking/agenda changes.
        
        Args:
            meeting_number: Meeting number
            contact_id: Contact ID (or None for unassignment)
            role_obj: Role object being assigned/unassigned
            action: 'assign' or 'unassign'
        """
        if not contact_id or not role_obj:
            return
        
        # Find roster entry for this contact in this meeting
        roster_entry = Roster.query.filter_by(
            meeting_number=meeting_number,
            contact_id=contact_id
        ).first()
        
        if not roster_entry:
            if action == 'assign':
                # Fetch contact details
                contact = db.session.get(Contact, contact_id)
                contact_type = contact.Type
                is_officer = (contact.user and contact.user.is_officer) or contact.Type == 'Officer'

                # Logic for Order Number
                new_order = None
                if is_officer:
                    # Officers get the next available order number starting from 1000
                    max_order = db.session.query(func.max(Roster.order_number)).filter(
                        Roster.meeting_number == meeting_number,
                        Roster.order_number >= 1000
                    ).scalar()
                    new_order = (max_order or 999) + 1
                else:
                    # Members/Guests get blank order number (None)
                    new_order = None

                # Logic for Ticket Class
                ticket_class = "Role Taker" # Default for Guest
                if is_officer:
                    ticket_class = "Officer"
                elif contact_type == 'Member':
                    ticket_class = "Member"

                roster_entry = Roster(
                    meeting_number=meeting_number,
                    contact_id=contact_id,
                    order_number=new_order,
                    ticket=ticket_class,
                    contact_type=contact_type
                )
                db.session.add(roster_entry)
            else:
                # Contact not in roster and we are unassigning - nothing to do
                return
        
        if action == 'assign':
            # Add role if not already assigned
            roster_entry.add_role(role_obj)
        elif action == 'unassign':
            # Remove role if assigned
            roster_entry.remove_role(role_obj)


class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    icon = db.Column(db.String(50))
    type = db.Column(db.String(20), nullable=False)
    award_category = db.Column(db.String(30))
    needs_approval = db.Column(db.Boolean, nullable=False)
    is_distinct = db.Column(db.Boolean, nullable=False)
    is_member_only = db.Column(db.Boolean, default=False)


class Vote(db.Model):
    __tablename__ = 'votes'
    id = db.Column(db.Integer, primary_key=True)
    meeting_number = db.Column(db.Integer, nullable=False)
    voter_identifier = db.Column(db.String(64), nullable=False)
    award_category = db.Column(db.Enum('speaker', 'evaluator', 'role-taker',
                               'table-topic', name='award_category_enum'), nullable=True)
    contact_id = db.Column(db.Integer, db.ForeignKey(
        'Contacts.id'), nullable=True)
    question = db.Column(db.String(255), nullable=True)
    score = db.Column(db.Integer, nullable=True)
    comments = db.Column(db.Text, nullable=True)

    # Relationship with Contact table
    contact = db.relationship('Contact', backref='votes')

    # Add index for performance
    __table_args__ = (
        db.Index('idx_meeting_voter', 'meeting_number', 'voter_identifier'),
    )

    @classmethod
    def delete_for_meeting(cls, meeting_number):
        """Deletes all votes for a meeting."""
        cls.query.filter_by(meeting_number=meeting_number).delete(synchronize_session=False)


class Achievement(db.Model):
    __tablename__ = 'achievements'
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'), nullable=False)
    member_id = db.Column(db.String(50))  # Redundant but requested
    issue_date = db.Column(db.Date, nullable=False)
    achievement_type = db.Column(db.Enum('level-completion', 'path-completion', 'program-completion', 
                                         name='achievement_type_enum'), nullable=False)
    path_name = db.Column(db.String(100))
    level = db.Column(db.Integer)
    notes = db.Column(db.Text)

    contact = db.relationship('Contact', backref='achievements')

