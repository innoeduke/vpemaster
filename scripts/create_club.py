import click
from flask.cli import with_appcontext
from app import db
from app.models.club import Club

@click.command('create-club')
@click.option('--club-no', required=True, help='The club number (unique ID)')
@click.option('--club-name', required=True, help='The full name of the club')
@with_appcontext
def create_club(club_no, club_name):
    """
    Creates a new club with the given club number and name.
    """
    # Check if club already exists
    existing_club = Club.query.filter_by(club_no=club_no).first()
    if existing_club:
        click.echo(f"Error: Club with number '{club_no}' already exists: {existing_club.club_name}")
        return

    try:
        new_club = Club(club_no=club_no, club_name=club_name)
        db.session.add(new_club)
        db.session.commit()
        click.echo(f"Successfully created club: {club_name} (No: {club_no})")
    except Exception as e:
        db.session.rollback()
        click.echo(f"Error creating club: {e}")
