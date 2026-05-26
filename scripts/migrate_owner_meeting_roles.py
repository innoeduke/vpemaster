import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.services.backup_service import BackupService

def migrate_owner_roles():
    app = create_app()
    with app.app_context():
        BackupService.migrate_owner_meeting_roles()

if __name__ == '__main__':
    migrate_owner_roles()
