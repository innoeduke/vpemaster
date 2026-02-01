
import click
from flask.cli import with_appcontext
from app.services.backup_parser import SQLBackupParser
from app.services.data_import_service import DataImportService

@click.command('import-data')
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

@click.command('fix-home-club')
@with_appcontext
def fix_home_club_command():
    """Fixes home club issues for all users."""
    print("Starting home club fix...")
    DataImportService.run_fix_home_clubs()
