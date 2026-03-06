from .base import db

class Ticket(db.Model):
    __tablename__ = 'tickets'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=False)
    price = db.Column(db.Float, default=0.0)
    type = db.Column(db.String(50))
    icon = db.Column(db.String(50)) # FontAwesome icon class
    color = db.Column(db.String(50)) # CSS color class or hex
    club_id = db.Column(db.Integer, db.ForeignKey('clubs.id'), nullable=True, index=True)

    club = db.relationship('Club', backref='tickets')

    @classmethod
    def get_by_name(cls, name, club_id=None):
        """Fetch a ticket by name, prioritizing club-specific over global."""
        from ..constants import GLOBAL_CLUB_ID
        if club_id and club_id != GLOBAL_CLUB_ID:
            ticket = cls.query.filter_by(name=name, club_id=club_id).first()
            if ticket:
                return ticket
        return cls.query.filter_by(name=name, club_id=GLOBAL_CLUB_ID).first()

    @classmethod
    def get_all_for_club(cls, club_id):
        """Fetch all tickets for a club, merging Global and Local items."""
        from ..constants import GLOBAL_CLUB_ID
        
        # Fetch Global items
        global_tickets = cls.query.filter_by(club_id=GLOBAL_CLUB_ID).all()
        
        # Fetch Local items
        local_tickets = []
        if club_id and club_id != GLOBAL_CLUB_ID:
            local_tickets = cls.query.filter_by(club_id=club_id).all()
            
        # Merge: Local overwrites Global by name
        merged = {t.name: t for t in global_tickets}
        for t in local_tickets:
            merged[t.name] = t
            
        return sorted(list(merged.values()), key=lambda x: x.id)

    def __repr__(self):
        return f'<Ticket {self.name}>'
