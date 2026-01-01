from . import db


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
    return User.query.get(int(user_id))

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
        return User.query.get(user_id)

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
                path_obj = db.session.query(Pathway).get(pp.path_id)
        
        return pp, path_obj

    def get_code(self, context_path_name=None):
        """
        Returns the project code based on a pathway context.
        """
        # Handle generic project
        if self.id == 60:
            return "TM1.0"

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
        if self.id == 60:
            return 1
            
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
    current_path_level = db.Column(db.String(10))
    pathway = db.Column(db.String(100))

    meeting = db.relationship('Meeting', backref='session_logs')
    project = db.relationship('Project', backref='session_logs')
    owner = db.relationship('Contact', backref='session_logs')
    session_type = db.relationship('SessionType', backref='session_logs')

    media = db.relationship('Media', backref='session_log',
                            uselist=False, cascade='all, delete-orphan')

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
        
        is_prepared_speech = self.project and self.project.Format == 'Prepared Speech'
        
        # Determine if this is a speech
        if (self.session_type.Valid_for_Project and self.Project_ID and self.Project_ID != 60) or is_prepared_speech:
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
                    # Try to find match with user's current path first
                    if self.owner and self.owner.Current_Path:
                        user_path = Pathway.query.filter_by(name=self.owner.Current_Path).first()
                        if user_path:
                            pp = PathwayProject.query.filter_by(
                                project_id=self.Project_ID, 
                                path_id=user_path.id
                            ).first()
                            if pp:
                                pathway_abbr = user_path.abbr
                                display_level = str(pp.level) if pp.level else "1"
                                project_code = f"{pathway_abbr}{pp.code}"
                                found_data = True
                    
                    # Fallback: any pathway
                    if not found_data:
                        pp = PathwayProject.query.filter_by(project_id=self.Project_ID).first()
                        if pp:
                            path_obj = Pathway.query.get(pp.path_id)
                            if path_obj:
                                pathway_abbr = path_obj.abbr
                                display_level = str(pp.level) if pp.level else "1"
                                project_code = f"{pathway_abbr}{pp.code}"
                                found_data = True

            # Priority 2: Use current_path_level if no canonical data found (or as supplement?)
            # Actually, if we found data, we trust DB. If not, use snapshot.
            if not found_data and self.current_path_level:
                match = re.match(r"([A-Z]+)(\d+)", self.current_path_level)
                if match:
                    pathway_abbr = match.group(1)
                    display_level = str(match.group(2))
                    project_code = self.current_path_level
        
        else:  # It's a role
            if self.current_path_level:
                match = re.match(r"([A-Z]+)(\d+)", self.current_path_level)
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
        """Update log pathway and sync with user profile if not a series."""
        if not pathway_name:
            return
            
        self.pathway = pathway_name
        
        # Sync to user profile if relevant
        if self.owner and self.owner.user:
            # Skip sync for presentation series
            if "Series" not in pathway_name:
                self.owner.user.Current_Path = pathway_name
                db.session.add(self.owner.user)

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
        from .models import Project, PathwayProject, Pathway
        
        project_name = "N/A"
        project_code = None
        current_pathway = self.owner.Current_Path if self.owner else "N/A"

        if self.Project_ID:
            project = Project.query.get(self.Project_ID)
            if project:
                project_name = project.Project_Name
                pp = PathwayProject.query.filter_by(project_id=project.id).first()
                if pp:
                    pathway_obj = Pathway.query.get(pp.path_id)
                    if pathway_obj:
                        current_pathway = pathway_obj.name
                        project_code = f"{pathway_obj.abbr}{pp.code}"

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


class Roster(db.Model):
    __tablename__ = 'roster'
    id = db.Column(db.Integer, primary_key=True)
    meeting_number = db.Column(db.Integer, nullable=False)
    order_number = db.Column(db.Integer, nullable=False)
    ticket = db.Column(db.String(20), nullable=True)
    contact_id = db.Column(db.Integer, db.ForeignKey(
        'Contacts.id'), nullable=True)
    contact_type = db.Column(db.String(50), nullable=True)

    contact = db.relationship('Contact', backref='roster_entries')


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

    # Relationship with Contact table
    contact = db.relationship('Contact', backref='votes')

    # Add index for performance
    __table_args__ = (
        db.Index('idx_meeting_voter', 'meeting_number', 'voter_identifier'),
    )


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

