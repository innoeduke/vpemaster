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
            BackupService._find_binary('mysqldump'),
            '--no-defaults',
            '-h', config['host'],
            '-u', config['user'],
            f"-p{config['password']}",
            '--no-tablespaces',
            '--set-gtid-purged=OFF',
            '--single-transaction',
            # f"--ignore-table={config['db']}.alembic_version", # Included version now for robustness
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
    def restore_database(filepath, db_name=None, upgrade=True, stamp_version=None):
        """Restores a database from a SQL dump."""
        if not os.path.exists(filepath):
            return False, "Backup file not found"
            
        config = BackupService._get_db_config()
        target_db = db_name or config['db']
        
        # 1. Clear existing columns to ensure no zombie structure
        clean_success, clean_msg = BackupService._clear_database()
        if not clean_success:
            return False, f"Cleanup failed: {clean_msg}"
            
        # 2. Apply SQL dump
        cmd = [
            BackupService._find_binary('mysql'),
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
            
            # 3. Synchronize schema if requested
            if upgrade:
                # Check if alembic_version exists after restore
                has_version = False
                try:
                    from sqlalchemy import inspect
                    from .. import db
                    inspector = inspect(db.engine)
                    has_version = 'alembic_version' in inspector.get_table_names()
                except Exception:
                    pass

                if not has_version:
                    # Legacy Backup detected! 
                    # We need to stamp it to an older version so 'upgrade' knows to work.
                    target_stamp = stamp_version or BackupService._get_parent_from_history()
                    
                    if target_stamp:
                        current_app.logger.info(f"Legacy backup detected (missing version table). Stamping to: {target_stamp}")
                        stamp_success, stamp_msg = BackupService._run_db_command(['stamp', target_stamp])
                        if not stamp_success:
                            return True, f"Restored but failed to stamp version {target_stamp}: {stamp_msg}"
                
                upgrade_success, upgrade_msg = BackupService._run_db_upgrade()
                if not upgrade_success:
                    return True, f"Database restored but upgrade failed: {upgrade_msg}"
                
                # 4. Final Validation Sanity Check
                valid, valid_msg = BackupService._validate_schema()
                if not valid:
                    return True, f"Database restored and upgraded, but {valid_msg}"
                    
                return True, f"Database restore and upgrade successful. {upgrade_msg}"
                
            return True, "Database restore successful"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def _clear_database():
        """Drops all tables in the current database."""
        try:
            from sqlalchemy import inspect, text
            from .. import db
            # We need an app context for this, which we should have from CLI
            
            inspector = inspect(db.engine)
            table_names = inspector.get_table_names()
            
            if not table_names:
                return True, "Database already empty"
                
            # Disable foreign key checks
            db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
            
            # Handle both tables and views if necessary, but tables is primary
            for table in table_names:
                db.session.execute(text(f"DROP TABLE IF EXISTS `{table}`;"))
            
            db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
            db.session.commit()
            
            return True, f"Dropped {len(table_names)} tables"
        except Exception as e:
            return False, str(e)

    @staticmethod
    def _find_binary(name):
        """Finds the path to a binary, looking in common locations."""
        # Try standard path
        import shutil
        if shutil.which(name):
            return shutil.which(name)
            
        # Try common Mac Homebrew paths
        common_paths = [
            f'/opt/homebrew/bin/{name}',
            f'/usr/local/bin/{name}',
            f'/usr/bin/{name}'
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
                
        return name # Fallback to name and hope for the best

    @staticmethod
    def _validate_schema():
        """Checks if key business columns exist in the DB after upgrade."""
        try:
            from sqlalchemy import inspect
            from .. import db
            # Need an app context
            inspector = inspect(db.engine)
            
            # Key indicator for the recent refactoring
            table_names = inspector.get_table_names()
            if 'user_clubs' not in table_names:
                 return True, "No user_clubs table found to validate."

            user_clubs_cols = [c['name'] for c in inspector.get_columns('user_clubs')]
            
            if 'auth_role_id' not in user_clubs_cols:
                return False, "Validation warning: 'auth_role_id' column is missing in 'user_clubs'. Restore may be inconsistent."
            
            return True, "Schema validation successful."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def _run_db_upgrade():
        """Runs flask db upgrade via subprocess to ensure environment parity."""
        return BackupService._run_db_command(['upgrade'])

    @staticmethod
    def _run_db_command(args):
        """Runs a flask db command safely."""
        try:
            flask_bin = BackupService._find_binary('flask')
            import sys
            if flask_bin == 'flask' and os.path.dirname(sys.executable):
                # Try sibling of the current python executable
                test_bin = os.path.join(os.path.dirname(sys.executable), 'flask')
                if os.path.exists(test_bin):
                    flask_bin = test_bin
                
            env = os.environ.copy()
            env['FLASK_APP'] = 'run.py' # Ensure FLASK_APP is set
            
            result = subprocess.run([flask_bin, 'db'] + args, capture_output=True, text=True, env=env)
            if result.returncode != 0:
                return False, result.stderr
            return True, result.stdout
        except Exception as e:
            return False, str(e)

    @staticmethod
    def _get_parent_from_history():
        """Parses flask db history to find the parent of the current head."""
        try:
            success, output = BackupService._run_db_command(['history'])
            if not success:
                return None
            
            # history output format: 
            # <prev> -> <head> (head), <comment>
            # We want the <prev> of the head line.
            lines = [l.strip() for l in output.split('\n') if '->' in l]
            if not lines:
                return None
            
            # The first line should be the head
            head_line = lines[0]
            if '(head)' in head_line:
                # Format: c7e8f9a0b1d2 -> e3a4db9468b7 (head)
                parts = head_line.split('->')
                if len(parts) >= 2:
                    parent = parts[0].strip()
                    # Return the id only
                    return parent.split(' ')[0]
            return None
        except Exception:
            return None

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
