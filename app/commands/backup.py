import os
import click
from flask.cli import with_appcontext
from ..services.backup_service import BackupService

@click.group()
def backup():
    """Database and resource backup management."""
    pass

@backup.command('create')
@click.option('--db/--no-db', default=True, help='Backup the database.')
@click.option('--resources/--no-resources', default=True, help='Backup static resources.')
@with_appcontext
def create_backup_command(db, resources):
    """Creates a new backup."""
    from flask import current_app
    backup_dir = os.path.join(current_app.instance_path, 'backup')
    
    if db:
        click.echo("Creating database backup...")
        db_dir = os.path.join(backup_dir, 'db')
        success, result = BackupService.create_database_backup(db_dir)
        if success:
            click.secho(f"Database backup created: {result}", fg='green')
        else:
            click.secho(f"Database backup failed: {result}", fg='red')
            
    if resources:
        click.echo("Creating resources backup...")
        res_dir = os.path.join(backup_dir, 'resources')
        success, result = BackupService.create_resources_backup(res_dir)
        if success:
            click.secho(f"Resources backup created: {result}", fg='green')
        else:
            click.secho(f"Resources backup failed: {result}", fg='red')

@backup.command('restore')
@click.option('--db-file', help='Path to database backup file.')
@click.option('--res-file', help='Path to resources backup file.')
@click.option('--latest', is_flag=True, help='Restore latest backups found.')
@with_appcontext
def restore_backup_command(db_file, res_file, latest):
    """Restores from a backup."""
    from flask import current_app
    backup_dir = os.path.join(current_app.instance_path, 'backup')
    
    if latest:
        if not db_file:
            db_file = BackupService.get_latest_backup(os.path.join(backup_dir, 'db'), 'backup_')
        if not res_file:
            res_file = BackupService.get_latest_backup(os.path.join(backup_dir, 'resources'), 'resources_')
            
    if db_file:
        click.echo(f"Restoring database from {db_file}...")
        success, message = BackupService.restore_database(db_file)
        if success:
            click.secho(message, fg='green')
        else:
            click.secho(message, fg='red')
            
    if res_file:
        click.echo(f"Restoring resources from {res_file}...")
        success, message = BackupService.restore_resources(res_file)
        if success:
            click.secho(message, fg='green')
        else:
            click.secho(message, fg='red')
            
    if not db_file and not res_file:
        click.echo("Nothing to restore. Provide --db-file, --res-file or --latest")
