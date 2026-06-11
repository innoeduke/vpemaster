import click
from flask.cli import with_appcontext
from app.services.backup_parser import SQLBackupParser
from app.services.data_import_service import DataImportService
from app.services.member_import_service import process_member_file
from app.models import Club
import io
import os

@click.group(name='import')
def import_group():
    """Import operations for data and members."""
    pass

@import_group.command('data')
@click.option('--file', required=True, help='Path to SQL backup file')
@click.option('--club-no', required=True, type=str, help='Club Number to associate data with')
@with_appcontext
def import_data(file, club_no):
    """Imports data from a SQL backup file."""
    print(f"Starting import from {file} for Club Number {club_no}...")
    
    parser = SQLBackupParser()
    try:
        data = parser.parse(file)
    except Exception as e:
        print(f"Error parsing file: {e}")
        return
    
    service = DataImportService(club_no)
    
    # 1. Execute DDL if needed
    if 'ddl' in data:
        print("Checking for missing tables...")
        service.create_tables(data['ddl'])
    
    # 2. Import Data
    # Import Clubs first to ensure Club Exists (if present in backup) or resolve existing
    if 'clubs' in data:
        service.import_clubs(data['clubs'])
        
    # Resolve Club ID after potential import
    service.resolve_club()
    
    if not service.club_id:
        print("ERROR: Club ID could not be resolved. Import aborted.")
        return
    
    try:
        if 'media' in data:
            service.import_media(data['media'])

        if 'contacts' in data:
            service.import_contacts(data['contacts'])
            
        if 'excomm' in data:
             # Depend on contacts
             service.import_excomm(data['excomm'])

        if 'meetings' in data:
            service.import_meetings(data['meetings'])

        if 'users' in data:
             service.import_users(data['users'])
        
        if 'meeting_roles' in data:
            service.import_meeting_roles(data['meeting_roles'])

        if 'session_types' in data:
            service.import_session_types(data['session_types'])

        if 'session_logs' in data:
            service.import_session_logs(data['session_logs'])
            
        if 'roster' in data:
            service.import_roster(data['roster'])

        if 'achievements' in data:
            service.import_achievements(data['achievements'])
            
        if 'votes' in data:
            service.import_votes(data['votes'])
            
            
        print("Running post-import fixes...")
        service.run_fix_home_clubs()
            
        print("Import completed successfully.")
        
    except Exception as e:
        print(f"Error during import: {e}")
        import traceback
        traceback.print_exc()

@import_group.command('members')
@click.option('--file', required=True, help='Path to CSV or XLSX file')
@click.option('--club-no', required=False, type=str, help='Club Number to import to. If omitted, prompts for selection.')
@with_appcontext
def import_members(file, club_no):
    """Imports members from a CSV or XLSX file."""
    if not club_no:
        clubs = Club.query.filter_by(status='active').all()
        if not clubs:
            print("No active clubs found in the system.")
            return
            
        print("Available Clubs:")
        for c in clubs:
            print(f"[{c.id}] {c.club_name} (Number: {c.club_number})")
            
        club_no_input = input("Enter Club ID to import members into: ")
        if not club_no_input.strip():
            print("Import aborted.")
            return
            
        try:
            club_id = int(club_no_input.strip())
        except ValueError:
            print("Invalid Club ID format. Aborted.")
            return
    else:
        club = Club.query.filter_by(club_number=club_no).first()
        if not club:
            print(f"Club with number {club_no} not found.")
            return
        club_id = club.id

    ext = file.rsplit('.', 1)[-1].lower() if '.' in file else ''
    if ext not in ['csv', 'xlsx']:
        print(f"Unsupported file type: {ext}. Only .csv and .xlsx are supported.")
        return

    print(f"Importing members into club ID {club_id} from {file}...")
    try:
        with open(file, 'rb') as f:
            file_bytes = f.read()
            success_count, failed_users = process_member_file(file_bytes, ext, club_id)
            print(f"Successfully imported/invited {success_count} members.")
            if failed_users:
                print("Failed rows:")
                for u in failed_users:
                    print(f"  - {u}")
    except Exception as e:
        print(f"Error importing members: {e}")
        import traceback
        traceback.print_exc()

@click.command('fix-home-club')
@with_appcontext
def fix_home_club_command():
    """Fixes home club issues for all users."""
    print("Starting home club fix...")
    DataImportService.run_fix_home_clubs()
