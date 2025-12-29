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

    mentor = db.relationship('Contact', remote_side=[id], foreign_keys=[Mentor_ID], backref='mentees')


from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from . import login_manager

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
    id = db.Column('ID', db.Integer, primary_key=True)
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
            path_obj = db.session.query(Pathway).filter_by(name=context_path_name).first()
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
    id = db.Column('ID', db.Integer, primary_key=True)
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
    GE_Style = db.Column(db.String(20), default='One shot')
    status = db.Column(db.Enum('unpublished', 'not started', 'running', 'finished', 'cancelled', name='meeting_status'),
                       default='unpublished', nullable=False)

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
    Project_ID = db.Column(db.Integer, db.ForeignKey('Projects.ID'))
    Start_Time = db.Column(db.Time)
    Duration_Min = db.Column(db.Integer, default=0)
    Duration_Max = db.Column(db.Integer)
    Notes = db.Column(db.String(1000))
    Status = db.Column(db.String(50))
    state = db.Column(db.String(50), nullable=False,
                      default='active')  # Can be 'active', 'waiting', 'cancelled'
    current_path_level = db.Column(db.String(10))

    meeting = db.relationship('Meeting', backref='session_logs')
    project = db.relationship('Project', backref='session_logs')
    owner = db.relationship('Contact', backref='session_logs')
    session_type = db.relationship('SessionType', backref='session_logs')

    media = db.relationship('Media', backref='session_log',
                            uselist=False, cascade='all, delete-orphan')


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
    project_id = db.Column(db.Integer, db.ForeignKey('Projects.ID'))
    code = db.Column(db.String(10))
    level = db.Column(db.Integer, nullable=True)
    type = db.Column(db.Enum('elective', 'required', 'other', name='pathway_project_type_enum'), nullable=False)


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

    # 添加与Contact表的关系
    contact = db.relationship('Contact', backref='votes')

    # 添加索引以提高查询性能
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

