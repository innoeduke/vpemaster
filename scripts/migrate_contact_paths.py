import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.services.backup_service import BackupService

def migrate_data():
    app = create_app()
    with app.app_context():
        BackupService.migrate_contact_pathways()

if __name__ == '__main__':
    migrate_data()
