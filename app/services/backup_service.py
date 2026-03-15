import os
import subprocess
import shutil
import time
from datetime import datetime
from flask import current_app
from urllib.parse import urlparse

class BackupService:
    @staticmethod
    def _get_db_config():
        """Extracts database configuration from SQLAlchemy URI."""
        uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
        if not uri:
            raise ValueError("SQLALCHEMY_DATABASE_URI not found in config")
        
        # Format: mysql+pymysql://user:password@host:port/dbname
        # We need to handle the prefix and potential query params
        
        # Remove prefix
        if '://' in uri:
            prefix, rest = uri.split('://', 1)
        else:
            rest = uri
            
        # Parse using urlparse (it expects a scheme, so we prepend one if missing)
        parsed = urlparse(f"dummy://{rest}")
        
        return {
            'user': parsed.username,
            'password': parsed.password,
            'host': parsed.hostname or '127.0.0.1',
            'port': parsed.port or 3306,
            'db': parsed.path.lstrip('/')
        }

    @staticmethod
    def create_database_backup(backup_dir):
        """Creates a database dump using mysqldump."""
        config = BackupService._get_db_config()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{config['db']}_{timestamp}.sql"
        filepath = os.path.join(backup_dir, filename)
        
        os.makedirs(backup_dir, exist_ok=True)
        
        # Command construction
        # Note: --no-defaults is used to avoid issues with local .my.cnf
        cmd = [
            'mysqldump',
            '--no-defaults',
            '-h', config['host'],
            '-u', config['user'],
            f"-p{config['password']}",
            '--no-tablespaces',
            '--set-gtid-purged=OFF',
            '--single-transaction',
            f"--ignore-table={config['db']}.alembic_version",
            config['db']
        ]
        
        try:
            with open(filepath, 'w') as f:
                result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
            
            if result.returncode != 0:
                # Cleanup failed file
                if os.path.exists(filepath):
                    os.remove(filepath)
                return False, f"mysqldump error: {result.stderr}"
                
            return True, filepath
        except Exception as e:
            return False, str(e)

    @staticmethod
    def create_resources_backup(backup_dir):
        """Creates a zip archive of static resource directories."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"resources_{timestamp}"
        filepath = os.path.join(backup_dir, filename)
        
        os.makedirs(backup_dir, exist_ok=True)
        
        # Directories to backup relative to app root
        resource_dirs = [
            'static/images',
            'static/mtg_templates',
            'static/club_resources',
            'static/uploads/avatars'
        ]
        
        # Use a temporary directory to gather files
        temp_dir = os.path.join(current_app.instance_path, 'temp_backup')
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            for rdir in resource_dirs:
                src = os.path.join(current_app.root_path, rdir)
                if os.path.exists(src):
                    dst = os.path.join(temp_dir, rdir)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src, dst)
            
            # Create archive
            archive_path = shutil.make_archive(filepath, 'zip', temp_dir)
            return True, archive_path
        except Exception as e:
            return False, str(e)
        finally:
            # Cleanup temp dir
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

    @staticmethod
    def restore_database(filepath, db_name=None):
        """Restores a database from a SQL dump."""
        if not os.path.exists(filepath):
            return False, "Backup file not found"
            
        config = BackupService._get_db_config()
        target_db = db_name or config['db']
        
        cmd = [
            'mysql',
            '--no-defaults',
            '-h', config['host'],
            '-u', config['user'],
            f"-p{config['password']}",
            target_db
        ]
        
        try:
            with open(filepath, 'r') as f:
                result = subprocess.run(cmd, stdin=f, stderr=subprocess.PIPE, text=True)
            
            if result.returncode != 0:
                return False, f"mysql restore error: {result.stderr}"
                
            return True, "Database restore successful"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def restore_resources(filepath):
        """Restores static resources from a zip archive."""
        if not os.path.exists(filepath):
            return False, "Resource backup file not found"
            
        try:
            # Extract directly into app root? 
            # The archive contains 'static/...' so we extract into app root
            shutil.unpack_archive(filepath, current_app.root_path, 'zip')
            return True, "Resources restore successful"
        except Exception as e:
            return False, str(e)

    @classmethod
    def get_latest_backup(cls, backup_dir, prefix):
        """Finds the latest file in backup_dir starting with prefix."""
        if not os.path.exists(backup_dir):
            return None
            
        files = [f for f in os.listdir(backup_dir) if f.startswith(prefix)]
        if not files:
            return None
            
        # Sort by mtime
        files.sort(key=lambda x: os.path.getmtime(os.path.join(backup_dir, x)), reverse=True)
        return os.path.join(backup_dir, files[0])
