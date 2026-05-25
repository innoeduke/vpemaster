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
        filename = f"backup_db_full_{timestamp}.sql"
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
                
            # Apply rotation
            BackupService._rotate_backups(backup_dir, 'db', 'sql')
            
            return True, filepath
        except Exception as e:
            return False, str(e)

    @staticmethod
    def create_resources_backup(backup_dir):
        """Creates a zip archive of static resource directories (legacy wrapper)."""
        return BackupService.create_file_backup(
            backup_dir,
            ['static/images', 'static/club_resources', 'static/uploads/avatars'],
            'resources',
            strategy='full'
        )

    @staticmethod
    def create_file_backup(backup_dir, target_dirs, resource_name, strategy='full'):
        """Creates a full or incremental backup of file directories."""
        import zipfile
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if strategy == 'increment':
            all_backups = BackupService.get_backups_sorted(backup_dir, resource_name, 'zip')
            if not all_backups:
                # Fallback to full
                return BackupService.create_file_backup(backup_dir, target_dirs, resource_name, strategy='full')
                
            latest_backup = all_backups[-1]
            baseline_time = latest_backup['timestamp']
            
            # Find changed files
            changed_files = []
            for target_dir in target_dirs:
                full_path = os.path.join(current_app.root_path, target_dir)
                if not os.path.exists(full_path):
                    continue
                if os.path.isdir(full_path):
                    for root, _, files in os.walk(full_path):
                        for file in files:
                            # Skip hidden files
                            if file.startswith('.'):
                                continue
                            file_path = os.path.join(root, file)
                            try:
                                file_mtime_dt = datetime.fromtimestamp(os.path.getmtime(file_path)).replace(microsecond=0)
                                if file_mtime_dt > baseline_time:
                                    arcname = os.path.relpath(file_path, current_app.root_path)
                                    changed_files.append((file_path, arcname))
                            except Exception:
                                continue
                else:
                    try:
                        file_mtime_dt = datetime.fromtimestamp(os.path.getmtime(full_path)).replace(microsecond=0)
                        if file_mtime_dt > baseline_time:
                            arcname = os.path.relpath(full_path, current_app.root_path)
                            changed_files.append((full_path, arcname))
                    except Exception:
                        continue
                        
            if not changed_files:
                return True, "No changes detected. Incremental backup skipped."
                
            filename = f"backup_{resource_name}_inc_{timestamp}.zip"
            filepath = os.path.join(backup_dir, filename)
            
            try:
                with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for fpath, arcname in changed_files:
                        zipf.write(fpath, arcname)
                return True, filepath
            except Exception as e:
                if os.path.exists(filepath):
                    os.remove(filepath)
                return False, str(e)
                
        else:  # strategy == 'full'
            filename = f"backup_{resource_name}_full_{timestamp}.zip"
            filepath = os.path.join(backup_dir, filename)
            
            try:
                with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for target_dir in target_dirs:
                        full_path = os.path.join(current_app.root_path, target_dir)
                        if not os.path.exists(full_path):
                            continue
                        if os.path.isdir(full_path):
                            for root, _, files in os.walk(full_path):
                                for file in files:
                                    if file.startswith('.'):
                                        continue
                                    file_path = os.path.join(root, file)
                                    arcname = os.path.relpath(file_path, current_app.root_path)
                                    zipf.write(file_path, arcname)
                        else:
                            arcname = os.path.relpath(full_path, current_app.root_path)
                            zipf.write(full_path, arcname)
                            
                # Apply rotation
                BackupService._rotate_backups(backup_dir, resource_name, 'zip')
                return True, filepath
            except Exception as e:
                if os.path.exists(filepath):
                    os.remove(filepath)
                return False, str(e)

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
        return BackupService.restore_file_backup(os.path.dirname(filepath), target_file=filepath, resource_name='resources')

    @staticmethod
    def restore_file_backup(backup_dir, target_file=None, latest=False, resource_name=None):
        """Restores full or incremental file backups."""
        if not os.path.exists(backup_dir) and not (target_file and os.path.isabs(target_file)):
            return False, f"Backup directory {backup_dir} does not exist."
            
        if target_file:
            if not os.path.isabs(target_file):
                target_file = os.path.abspath(os.path.join(backup_dir, target_file))
            backup_dir = os.path.dirname(target_file)
            
        all_backups = BackupService.get_backups_sorted(backup_dir, resource_name, 'zip')
        
        if latest:
            if not all_backups:
                return False, f"No backups found for {resource_name}."
            target_backup = all_backups[-1]
        else:
            if not target_file:
                return False, "Neither target file nor latest flag was specified."
            found = [b for b in all_backups if b['filepath'] == target_file or b['filename'] == os.path.basename(target_file)]
            if not found:
                if os.path.exists(target_file):
                    try:
                        shutil.unpack_archive(target_file, current_app.root_path, 'zip')
                        return True, f"Restored resource directly from file {os.path.basename(target_file)}."
                    except Exception as e:
                        return False, f"Failed to restore direct backup: {e}"
                return False, f"Backup file {target_file} not found."
            target_backup = found[0]
            
        # Perform restore
        if target_backup['type'] == 'full':
            try:
                shutil.unpack_archive(target_backup['filepath'], current_app.root_path, 'zip')
                return True, f"Full restore of {resource_name} successful from {target_backup['filename']}."
            except Exception as e:
                return False, f"Failed to restore {resource_name} full backup: {e}"
                
        # Incremental restore
        parent_full = None
        for b in reversed(all_backups):
            if b['timestamp'] < target_backup['timestamp'] and b['type'] == 'full':
                parent_full = b
                break
                
        if not parent_full:
            return False, f"Base full backup for incremental backup {target_backup['filename']} not found."
            
        chain = [parent_full]
        for b in all_backups:
            if parent_full['timestamp'] < b['timestamp'] <= target_backup['timestamp']:
                chain.append(b)
                
        try:
            for b in chain:
                shutil.unpack_archive(b['filepath'], current_app.root_path, 'zip')
            return True, f"Incremental restore of {resource_name} successful. Applied {len(chain)} backup(s) in order starting from {parent_full['filename']}."
        except Exception as e:
            return False, f"Failed to restore {resource_name} incremental backup chain: {e}"

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

    @staticmethod
    def get_backups_sorted(backup_dir, resource_name, ext):
        """Scans backup_dir, parses timestamps from filenames, and returns a list sorted chronologically."""
        if not os.path.exists(backup_dir):
            return []
        
        import re
        backups = []
        for filename in os.listdir(backup_dir):
            if resource_name == 'db':
                pattern = r"^backup_db_full_(\d{8})_(\d{6})\.sql$"
            else:
                pattern = rf"^backup_{resource_name}_(full|inc)_(\d{{8}})_(\d{{6}})\.{ext}$"
                
            match = re.match(pattern, filename)
            if match:
                if resource_name == 'db':
                    date_str, time_str = match.group(1), match.group(2)
                    btype = 'full'
                else:
                    btype, date_str, time_str = match.group(1), match.group(2), match.group(3)
                    
                try:
                    dt = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                    backups.append({
                        'filename': filename,
                        'filepath': os.path.join(backup_dir, filename),
                        'timestamp': dt,
                        'type': btype
                    })
                except ValueError:
                    continue
                    
        # Sort chronologically
        backups.sort(key=lambda x: x['timestamp'])
        return backups

    @staticmethod
    def _rotate_backups(backup_dir, resource_name, ext):
        """Rotates backups, keeping only the 5 most recent full backups and cleaning up associated incrementals."""
        all_backups = BackupService.get_backups_sorted(backup_dir, resource_name, ext)
        full_backups = [b for b in all_backups if b['type'] == 'full']
        
        if len(full_backups) > 5:
            # We need to keep only the most recent 5
            to_delete = full_backups[:-5]
            for fb in to_delete:
                # Delete full backup file
                if os.path.exists(fb['filepath']):
                    try:
                        os.remove(fb['filepath'])
                    except Exception:
                        pass
                        
                # Also delete associated incremental backups
                next_fb_idx = full_backups.index(fb) + 1
                next_fb_time = full_backups[next_fb_idx]['timestamp'] if next_fb_idx < len(full_backups) else datetime.max
                
                for b in all_backups:
                    if b['type'] == 'inc' and fb['timestamp'] <= b['timestamp'] < next_fb_time:
                        if os.path.exists(b['filepath']):
                            try:
                                os.remove(b['filepath'])
                            except Exception:
                                pass
