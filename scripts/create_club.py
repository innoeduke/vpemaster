import click
from flask.cli import with_appcontext
from app import db
from app.models.club import Club
from app.models.roster import MeetingRole
from app.models.session import SessionType
import csv
import os

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
        db.session.flush()  # Get new_club.id
        
        # Import Initial Data
        import_initial_data(new_club)
        
        db.session.commit()
        click.echo(f"Successfully created club: {club_name} (No: {club_no})")
    except Exception as e:
        db.session.rollback()
        click.echo(f"Error creating club: {e}")
        import traceback
        traceback.print_exc()

def import_initial_data(club):
    """Imports initial session types and meeting roles from CSV files."""
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    roles_csv = os.path.join(base_path, 'deploy', 'meeting_roles_new.csv')
    types_csv = os.path.join(base_path, 'deploy', 'session_types_new.csv')

    role_map = {} # Source CSV ID -> Target DB ID

    # 1. Import Meeting Roles
    if os.path.exists(roles_csv):
        with open(roles_csv, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                role = MeetingRole(
                    name=row['name'],
                    icon=row['icon'],
                    type=row['type'],
                    award_category=row.get('award_category'),
                    needs_approval=bool(int(row['needs_approval'] or 0)),
                    has_single_owner=bool(int(row['has_single_owner'] or 0)),
                    is_member_only=bool(int(row['is_member_only'] or 0)),
                    club_id=club.id
                )
                db.session.add(role)
                db.session.flush()
                role_map[row['id']] = role.id
        click.echo(f"Imported initial meeting roles for club {club.club_name}")
    else:
        click.echo(f"Warning: Meeting roles CSV not found at {roles_csv}")

    # 2. Import Session Types
    if os.path.exists(types_csv):
        with open(types_csv, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                st = SessionType(
                    Title=row['Title'],
                    Is_Section=bool(int(row['Is_Section'] or 0)),
                    Is_Hidden=bool(int(row['Is_Hidden'] or 0)),
                    Valid_for_Project=bool(int(row['Valid_for_Project'] or 0)),
                    Duration_Min=int(row['Duration_Min']) if row['Duration_Min'] else None,
                    Duration_Max=int(row['Duration_Max']) if row['Duration_Max'] else None,
                    role_id=role_map.get(row['role_id']),
                    club_id=club.id
                )
                db.session.add(st)
        click.echo(f"Imported initial session types for club {club.club_name}")
    else:
        click.echo(f"Warning: Session types CSV not found at {types_csv}")
