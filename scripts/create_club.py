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
@click.option('--skip-seed', is_flag=True, default=False, help='Skip seeding initial data (roles/types)')
@with_appcontext
def create_club(club_no, club_name, skip_seed):
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
        if not skip_seed:
            import_initial_data(new_club)
        else:
            click.echo("Skipping initial data seeding.")
        
        db.session.commit()
        click.echo(f"Successfully created club: {club_name} (No: {club_no})")
    except Exception as e:
        db.session.rollback()
        click.echo(f"Error creating club: {e}")
        import traceback
        traceback.print_exc()

def import_initial_data(club):
    """Imports initial session types and meeting roles from CSV files."""
    from app.constants import GLOBAL_CLUB_ID
    
    click.echo(f"Seeding data for {club.club_name} from Global Club (ID {GLOBAL_CLUB_ID})...")
    
    # 1. Copy Meeting Roles
    global_roles = MeetingRole.query.filter_by(club_id=GLOBAL_CLUB_ID).all()
    role_map = {} # Global Role ID -> New Role ID
    
    for gr in global_roles:
        new_role = MeetingRole(
            name=gr.name,
            icon=gr.icon,
            type=gr.type, 
            award_category=gr.award_category,
            needs_approval=gr.needs_approval,
            has_single_owner=gr.has_single_owner,
            is_member_only=gr.is_member_only,
            club_id=club.id
        )
        db.session.add(new_role)
        db.session.flush()
        role_map[gr.id] = new_role.id
        
    click.echo(f"Copied {len(global_roles)} meeting roles.")

    # 2. Copy Session Types
    global_types = SessionType.query.filter_by(club_id=GLOBAL_CLUB_ID).all()
    
    for gt in global_types:
        new_st = SessionType(
            Title=gt.Title,
            Is_Section=gt.Is_Section,
            Is_Hidden=gt.Is_Hidden,
            Valid_for_Project=gt.Valid_for_Project,
            Duration_Min=gt.Duration_Min,
            Duration_Max=gt.Duration_Max,
            role_id=role_map.get(gt.role_id), # Map to new role ID
            club_id=club.id
        )
        db.session.add(new_st)
    
    click.echo(f"Copied {len(global_types)} session types.")
