
import click
from flask.cli import with_appcontext
from app import db
from app.models.club import Club

@click.command('verify-reset')
@with_appcontext
def verify_reset():
    """Verifies that creating a club after cleanup gets ID 1."""
    
    # 1. Create a dummy club (if none exists) to bump sequence
    if not Club.query.first():
        c = Club(club_no="999999", club_name="Temp Club")
        db.session.add(c)
        db.session.commit()
        print(f"Created temp club with ID: {c.id}")
    
    # 2. Run cleanup (we'll call it programmatically or assume it's run)
    # Actually, let's just create a club and see its ID, assuming this runs AFTER cleanup
    
    c = Club(club_no="888888", club_name="Verification Club")
    db.session.add(c)
    db.session.commit()
    
    print(f"Created Verification Club with ID: {c.id}")
    if c.id == 1:
        print("SUCCESS: Club ID is 1")
    else:
        print(f"FAILURE: Club ID is {c.id}, expected 1")
    
    # Clean up
    db.session.delete(c)
    db.session.commit()
