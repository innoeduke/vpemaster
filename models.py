from vpemaster import db

class Contact(db.Model):
    __tablename__ = 'Contacts'
    id = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String(100))
    Type = db.Column(db.String(50), nullable=False)
    Club = db.Column(db.String(100))
    Date_Created = db.Column(db.Date)
    Working_Path = db.Column(db.String(50))
    Next_Project = db.Column(db.String(100))
    Completed_Levels = db.Column(db.String(255))
    DTM = db.Column(db.Boolean, default=False)


class SpeechLog(db.Model):
    __tablename__ = 'Speech_Logs'
    id = db.Column(db.Integer, primary_key=True)
    Meeting_Number = db.Column(db.Integer, nullable=True)
    Meeting_Date = db.Column(db.Date, nullable=True)
    Session = db.Column(db.String(50), nullable=False)
    Speech_Title = db.Column(db.String(255), nullable=True)
    Pathway = db.Column(db.String(100))
    Level = db.Column(db.String(50))
    Name = db.Column(db.String(100), nullable=False)
    Evaluator = db.Column(db.String(100))
    Project_Title = db.Column(db.String(255))
    Project_Type = db.Column(db.Integer)
    Project_Status = db.Column(db.String(50))
    Contact_ID = db.Column(db.Integer, nullable=False)
    Session_ID = db.Column(db.Integer, db.ForeignKey('Session_Logs.id'))


class User(db.Model):
    __tablename__ = 'Users'
    id = db.Column(db.Integer, primary_key=True)
    Username = db.Column(db.String(50), nullable=False)
    Contact_ID = db.Column(db.Integer, default=0)
    Pass_Hash = db.Column(db.String(255), nullable=False)
    Full_Name = db.Column(db.String(255))
    Display_Name = db.Column(db.String(255))
    Date_Created = db.Column(db.Date)
    Role = db.Column(db.String(255), nullable=False)


class Project(db.Model):
    __tablename__ = 'Projects'
    ID = db.Column(db.Integer, primary_key=True)
    Project_Name = db.Column(db.String(255))
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

class Meeting(db.Model):
    __tablename__ = 'Meetings'
    ID = db.Column(db.Integer, primary_key=True)
    Meeting_Number = db.Column(db.SmallInteger, unique=True)
    Meeting_Date = db.Column(db.Date)
    Start_Time = db.Column(db.Time)
    Meeting_Template = db.Column(db.String(100))
    WOD = db.Column(db.String(100))
    Best_TT_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    Best_Evaluator_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    Best_Speaker_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    Best_Roletaker_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'))

class SessionType(db.Model):
    __tablename__ = 'Session_Types'
    id = db.Column(db.Integer, primary_key=True)
    Title = db.Column(db.String(255))
    Default_Owner = db.Column(db.String(255))
    Is_Section = db.Column(db.Boolean, default=False)
    Is_Titleless = db.Column(db.Boolean, default=True)
    Duration_Min = db.Column(db.Integer)
    Duration_Max = db.Column(db.Integer)


class SessionLog(db.Model):
    __tablename__ = 'Session_Logs'
    id = db.Column(db.Integer, primary_key=True)
    Meeting_Number = db.Column(db.SmallInteger, db.ForeignKey('Meetings.Meeting_Number'))
    Meeting_Seq = db.Column(db.Integer)
    Session_Title = db.Column(db.String(255))
    Type_ID = db.Column(db.Integer, db.ForeignKey('Session_Types.id'))
    Owner_ID = db.Column(db.Integer, db.ForeignKey('Contacts.id'))
    Project_ID = db.Column(db.Integer, db.ForeignKey('Projects.ID'))
    Start_Time = db.Column(db.Time)
    Duration_Min = db.Column(db.Integer)
    Duration_Max = db.Column(db.Integer)
    Notes = db.Column(db.String(1000))