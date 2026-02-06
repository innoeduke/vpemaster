"""
Flask CLI commands for packing and unpacking backup data.

Usage:
    flask pack   - Create a zip with avatars folder and latest backup SQL
    flask unpack - Restore avatars folder and backup SQL from zip
"""
import click
import os
import re
import zipfile
from datetime import datetime
from flask import current_app
from flask.cli import with_appcontext


# Constants for paths (relative to app root)
UPLOADS_REL_PATH = 'app/static/uploads'
BACKUP_REL_PATH = 'instance/backup'
OUTPUT_REL_PATH = 'instance'
BACKUP_PATTERN = r'^backup_vpemaster_(\d{8})_(\d{6})\.sql$'


def get_app_root():
    """Get the application root directory."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def find_latest_backup(backup_dir):
    """
    Find the most recent backup file matching the pattern.
    Returns (filename, datetime) tuple or (None, None) if not found.
    """
    latest_file = None
    latest_dt = None
    
    if not os.path.exists(backup_dir):
        return None, None
    
    pattern = re.compile(BACKUP_PATTERN)
    
    for filename in os.listdir(backup_dir):
        match = pattern.match(filename)
        if match:
            date_str = match.group(1)  # yyyymmdd
            time_str = match.group(2)  # hhmmss
            try:
                dt = datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
                if latest_dt is None or dt > latest_dt:
                    latest_dt = dt
                    latest_file = filename
            except ValueError:
                continue
    
    return latest_file, latest_dt


@click.command('pack')
@click.option('--output', '-o', default=None, help='Output zip filename (default: instance/vpemaster_backup_<timestamp>.zip)')
@with_appcontext
def pack(output):
    """Pack uploads folder and latest backup SQL into a zip file."""
    app_root = get_app_root()
    
    # Generate output filename if not provided
    if output is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output = f'vpemaster_backup_{timestamp}.zip'
    
    # Ensure output path is in instance/ folder if not absolute
    if not os.path.isabs(output):
        output = os.path.join(app_root, OUTPUT_REL_PATH, output)
    
    uploads_path = os.path.join(app_root, UPLOADS_REL_PATH)
    backup_dir = os.path.join(app_root, BACKUP_REL_PATH)
    
    # Find latest backup file
    backup_file, backup_dt = find_latest_backup(backup_dir)
    
    if backup_file is None:
        click.echo("⚠️  Warning: No backup file matching pattern 'backup_vpemaster_yyyymmdd_hhmmss.sql' found.", err=True)
    else:
        click.echo(f"📄 Found latest backup: {backup_file} ({backup_dt.strftime('%Y-%m-%d %H:%M:%S')})")
    
    # Check if uploads folder exists
    if not os.path.exists(uploads_path):
        click.echo(f"⚠️  Warning: Uploads folder not found at {UPLOADS_REL_PATH}", err=True)
    
    # Create zip file
    try:
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zipf:
            items_added = 0
            
            # Add uploads folder
            if os.path.exists(uploads_path):
                for root, dirs, files in os.walk(uploads_path):
                    for file in files:
                        if file.startswith('.'):  # Skip hidden files
                            continue
                        file_path = os.path.join(root, file)
                        # Store with relative path preserving folder structure
                        arcname = os.path.relpath(file_path, app_root)
                        zipf.write(file_path, arcname)
                        items_added += 1
                click.echo(f"📁 Added {items_added} files from {UPLOADS_REL_PATH}")
            
            # Add latest backup SQL
            if backup_file:
                backup_file_path = os.path.join(backup_dir, backup_file)
                arcname = os.path.join(BACKUP_REL_PATH, backup_file)
                zipf.write(backup_file_path, arcname)
                click.echo(f"📄 Added {backup_file}")
                items_added += 1
            
            if items_added == 0:
                click.echo("❌ No files to pack!", err=True)
                os.remove(output)
                return
        
        # Get file size for display
        size_bytes = os.path.getsize(output)
        size_kb = size_bytes / 1024
        if size_kb > 1024:
            size_str = f"{size_kb / 1024:.2f} MB"
        else:
            size_str = f"{size_kb:.2f} KB"
        
        click.echo(f"✅ Created: {output} ({size_str})")
        
    except Exception as e:
        click.echo(f"❌ Error creating zip file: {e}", err=True)
        if os.path.exists(output):
            os.remove(output)
        raise


@click.command('unpack')
@click.argument('zipfile_path')
@with_appcontext
def unpack(zipfile_path):
    """Unpack uploads folder and backup SQL from a zip file (overwrites existing files)."""
    app_root = get_app_root()
    
    # Resolve zipfile path - check instance/ folder first if not absolute
    if not os.path.isabs(zipfile_path):
        zipfile_path = os.path.join(app_root, zipfile_path)
    
    if not os.path.exists(zipfile_path):
        click.echo(f"❌ Error: Zip file not found: {zipfile_path}", err=True)
        return
    
    try:
        with zipfile.ZipFile(zipfile_path, 'r') as zipf:
            # List contents
            namelist = zipf.namelist()
            
            upload_files = [n for n in namelist if n.startswith(UPLOADS_REL_PATH)]
            backup_files = [n for n in namelist if n.startswith(BACKUP_REL_PATH) and n.endswith('.sql')]
            
            click.echo(f"📦 Zip contains:")
            click.echo(f"   - {len(upload_files)} upload file(s)")
            click.echo(f"   - {len(backup_files)} backup SQL file(s)")
            
            if not upload_files and not backup_files:
                click.echo("❌ No recognized files in zip!", err=True)
                return
            
            # Extract files (overwrite existing)
            extracted_count = 0
            for name in namelist:
                if name.startswith(UPLOADS_REL_PATH) or (name.startswith(BACKUP_REL_PATH) and name.endswith('.sql')):
                    target_path = os.path.join(app_root, name)
                    
                    # Ensure parent directory exists
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    
                    # Extract file
                    with zipf.open(name) as source:
                        with open(target_path, 'wb') as target:
                            target.write(source.read())
                    extracted_count += 1
            
            click.echo(f"\n✅ Extracted {extracted_count} file(s) successfully!")
            
            if upload_files:
                click.echo(f"   📁 Uploads restored to: {UPLOADS_REL_PATH}")
            if backup_files:
                for bf in backup_files:
                    click.echo(f"   📄 Backup restored: {os.path.basename(bf)}")
                    
    except zipfile.BadZipFile:
        click.echo(f"❌ Error: Invalid zip file: {zipfile_path}", err=True)
    except Exception as e:
        click.echo(f"❌ Error extracting zip file: {e}", err=True)
        raise
