from .base import db

class Ticket(db.Model):
    __tablename__ = 'tickets'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    price = db.Column(db.Float, default=0.0)
    icon = db.Column(db.String(50)) # FontAwesome icon class
    color = db.Column(db.String(50)) # CSS color class or hex

    def __repr__(self):
        return f'<Ticket {self.name}>'
