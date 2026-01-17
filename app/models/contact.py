"""Contact model for member and guest information."""
from .base import db


class Contact(db.Model):
    __tablename__ = 'Contacts'
    id = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String(100), nullable=False, unique=True)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    Email = db.Column(db.String(120), unique=True, nullable=True)
    Type = db.Column(db.String(50), nullable=False, default='Guest')
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
    
    def update_name_from_parts(self):
        """Auto-populate Name from first_name and last_name if Name is blank."""
        if not self.Name and (self.first_name or self.last_name):
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
    
    def get_primary_club(self):
        """Get the primary club for this contact."""
        from .contact_club import ContactClub
        cc = ContactClub.query.filter_by(contact_id=self.id, is_primary=True).first()
        return cc.club if cc else None
    
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

