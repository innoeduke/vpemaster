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


class User(db.Model):
    __tablename__ = 'Users'
    id = db.Column(db.Integer, primary_key=True)
    Username = db.Column(db.String(50), nullable=False, unique=True)
    Email = db.Column(db.String(120), unique=True, nullable=True)
    Member_ID = db.Column(db.String(50), unique=True, nullable=True)
    Mentor_ID = db.Column(db.Integer, db.ForeignKey(
        'Contacts.id'), nullable=True)
    Contact_ID = db.Column(db.Integer, db.ForeignKey(
        'Contacts.id'), nullable=True, unique=True)
    Pass_Hash = db.Column(db.String(255), nullable=False)
    Date_Created = db.Column(db.Date)
    Role = db.Column(db.String(50), nullable=False, default='Member')
    Status = db.Column(db.String(50), nullable=False, default='active')
    Current_Path = db.Column(db.String(50), nullable=True)
    Next_Project = db.Column(db.String(100), nullable=True)
    Credential = db.Column(db.String(10), nullable=True)
    contact = db.relationship('Contact', foreign_keys=[Contact_ID], backref=db.backref('user', uselist=False))
    mentor = db.relationship('Contact', foreign_keys=[Mentor_ID])


class Project(db.Model):
    __tablename__ = 'Projects'
    ID = db.Column(db.Integer, primary_key=True)
    Project_Name = db.Column(db.String(255), nullable=False)
    Format = db.Column(db.String(50))
    Duration_Min = db.Column(db.Integer)
    Duration_Max = db.Column(db.Integer)
    Introduction = db.Column(db.String(1000))
    Overview = db.Column(db.String(1000))
    Purpose = db.Column(db.String(255))
    Requirements = db.Column(db.String(500))
    Resources = db.Column(db.String(500))
    Code_DL = db.Column(db.String(5))
    Code_EH = db.Column(db.String(5))
    Code_MS = db.Column(db.String(5))
    Code_PI = db.Column(db.String(5))
    Code_PM = db.Column(db.String(5))
    Code_VC = db.Column(db.String(5))
    Code_DTM = db.Column(db.String(5))


class Meeting(db.Model):
    __tablename__ = 'Meetings'
    ID = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(255), default='Keynote Speech')
    Meeting_Number = db.Column(db.SmallInteger, unique=True, nullable=False)
    Meeting_Date = db.Column(db.Date)
    Meeting_Title = db.Column(db.String(255))
    Subtitle = db.Column(db.String(255), nullable=True)
    Start_Time = db.Column(db.Time)
    Meeting_Template = db.Column(db.String(100))
    WOD = db.Column(db.String(100))
    Best_TT_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    Best_Evaluator_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    Best_Speaker_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    Best_Roletaker_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    media_id = db.Column(db.Integer, db.ForeignKey('Media.id', use_alter=True))
    GE_Style = db.Column(db.String(20), default='One shot')

    best_tt_speaker = db.relationship('Contact', foreign_keys=[Best_TT_ID])
    best_evaluator = db.relationship(
        'Contact', foreign_keys=[Best_Evaluator_ID])
    best_speaker = db.relationship('Contact', foreign_keys=[Best_Speaker_ID])
    best_roletaker = db.relationship(
        'Contact', foreign_keys=[Best_Roletaker_ID])
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
    Designation = db.Column(db.String(255), default='')
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


class Presentation(db.Model):
    __tablename__ = 'presentations'
    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.SmallInteger, nullable=False)
    code = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    series = db.Column(db.String(100))


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
    contact_id = db.Column(db.Integer, db.ForeignKey('Contacts.id'), nullable=True)

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
