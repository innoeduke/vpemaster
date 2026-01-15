"""Contact model for member and guest information."""
from .base import db


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
        from .session import SessionLog
        
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
        from .achievement import Achievement
        
        if not pathway_name:
            return set()
        
        achievements = Achievement.query.filter_by(
            contact_id=self.id,
            path_name=pathway_name,
            achievement_type='level-completion'
        ).all()
        return {a.level for a in achievements if a.level}
