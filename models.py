from . import db

class Contact(db.Model):
    __tablename__ = 'Contacts'
    id = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String(100), nullable=False, unique=True)
    Email = db.Column(db.String(120), unique=True, nullable=True)
    Type = db.Column(db.String(50), nullable=False, default='Guest')
    Club = db.Column(db.String(100))
    Date_Created = db.Column(db.Date)
    Working_Path = db.Column(db.String(50))
    Next_Project = db.Column(db.String(100))
    Completed_Levels = db.Column(db.String(255))
    DTM = db.Column(db.Boolean, default=False)
    Phone_Number = db.Column(db.String(50), nullable=True)
    Bio = db.Column(db.Text, nullable=True)

class User(db.Model):
    __tablename__ = 'Users'
    id = db.Column(db.Integer, primary_key=True)
    Username = db.Column(db.String(50), nullable=False, unique=True)
    Email = db.Column(db.String(120), unique=True, nullable=True)
    Member_ID = db.Column(db.String(50), unique=True, nullable=True)
    Mentor_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'), nullable=True)
    Contact_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'), nullable=True)
    Pass_Hash = db.Column(db.String(255), nullable=False)
    Date_Created = db.Column(db.Date)
    Role = db.Column(db.String(50), nullable=False, default='Member')
    Status = db.Column(db.String(50), nullable=False, default='active')
    contact = db.relationship('Contact', foreign_keys=[Contact_ID])
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
    Meeting_Number = db.Column(db.SmallInteger, unique=True, nullable=False)
    Meeting_Date = db.Column(db.Date)
    Start_Time = db.Column(db.Time)
    Meeting_Template = db.Column(db.String(100))
    WOD = db.Column(db.String(100))
    Best_TT_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    Best_Evaluator_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    Best_Speaker_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    Best_Roletaker_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    GE_Style = db.Column(db.String(20), default='immediate')

class SessionType(db.Model):
    __tablename__ = 'Session_Types'
    id = db.Column(db.Integer, primary_key=True)
    Title = db.Column(db.String(255), nullable=False, unique=True)
    Default_Owner = db.Column(db.String(255))
    Is_Section = db.Column(db.Boolean, default=False)
    Is_Hidden = db.Column(db.Boolean, default=False)
    Predefined = db.Column(db.Boolean, default=True)
    Role = db.Column(db.String(255), default='')
    Role_Group = db.Column(db.String(50))
    Valid_for_Project = db.Column(db.Boolean, default=False)
    Duration_Min = db.Column(db.Integer)
    Duration_Max = db.Column(db.Integer)

class SessionLog(db.Model):
    __tablename__ = 'Session_Logs'
    id = db.Column(db.Integer, primary_key=True)
    Meeting_Number = db.Column(db.SmallInteger, db.ForeignKey('Meetings.Meeting_Number'), nullable=False)
    Meeting_Seq = db.Column(db.Integer)
    Session_Title = db.Column(db.String(255)) # For custom titles like speeches
    Type_ID = db.Column(db.Integer, db.ForeignKey('Session_Types.id'), nullable=False)
    Owner_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    Designation = db.Column(db.String(255), default='')
    Project_ID = db.Column(db.Integer, db.ForeignKey('Projects.ID'))
    Start_Time = db.Column(db.Time)
    Duration_Min = db.Column(db.Integer)
    Duration_Max = db.Column(db.Integer)
    Notes = db.Column(db.String(1000))
    Status = db.Column(db.String(50)) # New field for 'Booked', 'Completed'

    meeting = db.relationship('Meeting', backref='session_logs')
    project = db.relationship('Project', backref='session_logs')
    owner = db.relationship('Contact', backref='session_logs')
    session_type = db.relationship('SessionType', backref='session_logs')

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