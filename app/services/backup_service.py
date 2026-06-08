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
            ['static/images', 'static/club_resources', 'static/avatars'],
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

    @staticmethod
    def sync_remote_backup(resource_name, remote_user, remote_host, remote_base_path, password=None):
        """Syncs backup files of the given resource_name from remote server to local."""
        import tempfile
        import stat
        import shlex
        import subprocess
        import click
        from flask import current_app

        # 1. Pre-pull: check/prepare local directory
        local_dir = os.path.abspath(os.path.join(current_app.instance_path, 'backup', resource_name))
        os.makedirs(local_dir, exist_ok=True)

        # 2. Check connection / set up env for SSH_ASKPASS
        env = os.environ.copy()
        askpass_path = None
        if password:
            fd, askpass_path = tempfile.mkstemp()
            try:
                with os.fdopen(fd, 'w') as f:
                    f.write(f"#!/bin/sh\necho {shlex.quote(password)}\n")
                os.chmod(askpass_path, stat.S_IRUSR | stat.S_IXUSR)
                env['SSH_ASKPASS'] = askpass_path
                env['DISPLAY'] = ':0'
                env['SSH_ASKPASS_REQUIRE'] = 'force'
            except Exception as e:
                if askpass_path and os.path.exists(askpass_path):
                    os.remove(askpass_path)
                return False, f"Failed to prepare password agent: {e}"

        try:
            # Check SSH connection
            ssh_cmd = ["ssh", "-o", "ConnectTimeout=5", f"{remote_user}@{remote_host}", "exit"]
            res = subprocess.run(ssh_cmd, env=env, capture_output=True, text=True)
            if res.returncode != 0:
                err_msg = res.stderr.strip() or "SSH connection failed."
                return False, f"SSH connection check failed: {err_msg}"

            # 3. Pull: Sync directories using rsync
            remote_path = f"{remote_user}@{remote_host}:{remote_base_path}/{resource_name}/"
            local_path = local_dir + "/"

            click.echo(f"Syncing remote {remote_path} to local {local_path}...")
            rsync_cmd = [
                "rsync",
                "-avz",
                "--delete",
                "-e", "ssh -o ConnectTimeout=5",
                remote_path,
                local_path
            ]
            res_rsync = subprocess.run(rsync_cmd, env=env)
            if res_rsync.returncode != 0:
                return False, "Rsync command returned non-zero exit status."

            # List synced files
            files = [f for f in os.listdir(local_dir) if os.path.isfile(os.path.join(local_dir, f)) and not f.startswith('.')]
            if files:
                click.secho(f"📄 Synced files in backup/{resource_name}:", fg='cyan', bold=True)
                for f in sorted(files):
                    click.secho(f"  - {f}", fg='green')

            return True, f"Successfully synced {resource_name} backups."
        finally:
            if askpass_path and os.path.exists(askpass_path):
                try:
                    os.remove(askpass_path)
                except Exception:
                    pass

    @staticmethod
    def migrate_contact_pathways():
        """Migrate legacy contact pathway columns to ContactPath junction table."""
        import re
        from datetime import date
        from app import db
        from app.models import Contact, Pathway, ContactPath, Achievement, SessionLog

        # Load all pathways for reference
        pathways = Pathway.query.all()
        pathway_by_name = {p.name.strip().lower(): p for p in pathways if p.name}
        pathway_by_abbr = {p.abbr.strip().upper(): p for p in pathways if p.abbr}
        
        contacts = Contact.query.all()
        contacts_updated_count = 0
        
        for contact in contacts:
            legacy_current = contact._Current_Path
            legacy_completed = contact._Completed_Paths
            
            if not legacy_current and not legacy_completed:
                continue
                
            contact_header_printed = False
            def print_contact_header():
                nonlocal contact_header_printed, contacts_updated_count
                if not contact_header_printed:
                    print(f"\nProcessing Contact: {contact.Name} (ID: {contact.id})")
                    contact_header_printed = True
                    contacts_updated_count += 1

            # Retrieve achievements for this contact's user
            uid = contact.user_id
            achievements = []
            if uid:
                achievements = Achievement.query.filter_by(user_id=uid).all()
            
            registered_pathway_ids = set()
            
            # 1. Migrate completed paths
            if legacy_completed:
                parts = [p.strip() for p in legacy_completed.split('/') if p.strip()]
                for part in parts:
                    match = re.match(r"^([A-Z]+)\d*$", part.upper())
                    abbr = match.group(1) if match else part
                    
                    pathway = pathway_by_abbr.get(abbr.upper()) or pathway_by_name.get(part.lower())
                    if pathway:
                        if pathway.id in registered_pathway_ids:
                            continue
                            
                        # Find completed date from achievements
                        completed_date = None
                        path_ach = next((a for a in achievements if a.achievement_type == 'path-completion' and a.path_name == pathway.name), None)
                        if path_ach:
                            completed_date = path_ach.award_date
                        else:
                            lvl5_ach = next((a for a in achievements if a.achievement_type == 'level-completion' and a.path_name == pathway.name and a.level == 5), None)
                            if lvl5_ach:
                                completed_date = lvl5_ach.award_date
                        
                        # Check if already registered
                        existing_cp = ContactPath.query.filter_by(contact_id=contact.id, path_id=pathway.id).first()
                        if existing_cp:
                            continue

                        # Create ContactPath
                        cp = ContactPath(
                            contact_id=contact.id,
                            path_id=pathway.id,
                            status='completed',
                            is_default=False,
                            registered_date=date.today(),
                            completed_date=completed_date
                        )
                        db.session.add(cp)
                        registered_pathway_ids.add(pathway.id)
                        print_contact_header()
                        print(f"  - Completed Path: {pathway.name} (Completed: {completed_date})")
            
            # 2. Migrate current (default) path
            if contact.Type == 'Guest' and legacy_current:
                contact._Current_Path = None
                print_contact_header()
                print(f"  - Cleared wrong Current_Path for Guest: {legacy_current}")
            elif legacy_current:
                pathway = pathway_by_name.get(legacy_current.strip().lower()) or pathway_by_abbr.get(legacy_current.strip().upper())
                if pathway:
                    if pathway.id in registered_pathway_ids:
                        cp = ContactPath.query.filter_by(contact_id=contact.id, path_id=pathway.id).first()
                        if cp and not cp.is_default:
                            cp.is_default = True
                            print_contact_header()
                            print(f"  - Set existing completed path {pathway.name} as default")
                    else:
                        existing_cp = ContactPath.query.filter_by(contact_id=contact.id, path_id=pathway.id).first()
                        if existing_cp:
                            if not existing_cp.is_default or existing_cp.status != 'working':
                                existing_cp.is_default = True
                                existing_cp.status = 'working'
                                print_contact_header()
                                print(f"  - Updated existing ContactPath as default working: {pathway.name}")
                        else:
                            cp = ContactPath(
                                contact_id=contact.id,
                                path_id=pathway.id,
                                status='working',
                                is_default=True,
                                registered_date=date.today(),
                                completed_date=None
                            )
                            db.session.add(cp)
                            print_contact_header()
                            print(f"  - Working Path (Default): {pathway.name}")
                        registered_pathway_ids.add(pathway.id)
            
        # 3. Update SessionLogs
        session_logs_updated = SessionLog.query.filter(
            SessionLog.Project_ID.is_(None),
            SessionLog.pathway.isnot(None)
        ).all()
        
        if session_logs_updated:
            print("\nUpdating SessionLogs to pair project_id and pathway...")
            for log in session_logs_updated:
                log.pathway = None
            print(f"  - Set pathway to NULL for {len(session_logs_updated)} SessionLogs with no Project_ID.")

        db.session.commit()
        if contacts_updated_count > 0:
            print(f"\nSuccessfully migrated {contacts_updated_count} updated contacts!")

    @staticmethod
    def migrate_owner_meeting_roles():
        """Back-fill target_pathway and target_level for owner_meeting_roles."""
        from datetime import date
        from app import db
        from app.models import OwnerMeetingRoles

        omrs = OwnerMeetingRoles.query.filter(
            db.or_(
                OwnerMeetingRoles.target_pathway.is_(None),
                OwnerMeetingRoles.target_level.is_(None)
            )
        ).all()
        
        updated_count = 0
        
        for omr in omrs:
            contact = omr.contact
            meeting = omr.meeting
            
            # Skip guests or records with no contact
            if not contact or contact.Type == 'Guest':
                continue
                
            meeting_date = meeting.Meeting_Date if meeting and meeting.Meeting_Date else date.today()
            
            # 1. Resolve target_pathway
            resolved_pathway = None
            
            # 1a. Check associated session log's pathway
            if omr.session_log and omr.session_log.pathway:
                resolved_pathway = omr.session_log.pathway
                
            # 1b. Check contact's active pathways at the time of the meeting
            if not resolved_pathway:
                active_paths = [
                    cp for cp in contact.registered_paths
                    if cp.registered_date and cp.registered_date <= meeting_date
                    and (not cp.completed_date or cp.completed_date >= meeting_date)
                ]
                if active_paths:
                    default_cp = next((cp for cp in active_paths if cp.is_default), active_paths[0])
                    if default_cp.pathway:
                        resolved_pathway = default_cp.pathway.name
                        
            # 1c. Fallback to Contact's Current_Path
            if not resolved_pathway:
                resolved_pathway = contact.Current_Path
                
            if not resolved_pathway:
                continue
                
            # 2. Resolve target_level
            resolved_level = str(contact.get_active_level_at_date(resolved_pathway, meeting_date))
            
            # 3. Apply updates
            modified = False
            if not omr.target_pathway:
                omr.target_pathway = resolved_pathway
                modified = True
            if not omr.target_level:
                omr.target_level = resolved_level
                modified = True
                
            if modified:
                if updated_count == 0:
                    print("Starting back-fill of target_pathway and target_level for owner_meeting_roles...")
                updated_count += 1
                print(f"  - Updated OMR (ID: {omr.id}) for {contact.Name} at meeting on {meeting_date}: {resolved_pathway} L{resolved_level}")
                
        db.session.commit()
        if updated_count > 0:
            print(f"\nSuccessfully back-filled {updated_count} owner_meeting_roles records!")
