from vpemaster import db

class Contact(db.Model):
    __tablename__ = 'Contacts'
    id = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String(100))
    Club = db.Column(db.String(100))
    Date_Created = db.Column(db.Date)
    Current_Project = db.Column(db.String(100))
    Completed_Levels = db.Column(db.String(255))


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


class User(db.Model):
    __tablename__ = 'Users'
    id = db.Column(db.Integer, primary_key=True)
    Username = db.Column(db.String(50), nullable=False)
    Pass_Hash = db.Column(db.String(255), nullable=False)
    Full_Name = db.Column(db.String(255))
    Display_Name = db.Column(db.String(255))
    Date_Created = db.Column(db.Date)
    Role = db.Column(db.String(255), nullable=False)
