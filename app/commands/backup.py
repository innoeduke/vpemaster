import os
import click
from flask.cli import with_appcontext
from ..services.backup_service import BackupService

@click.group('resources')
def resources():
    """Database and resource backup management."""
    pass

# --- DB Command Group ---
@resources.group('db')
def db_group():
    """Database backup operations."""
    pass

@db_group.command('backup')
@with_appcontext
def db_backup():
    """Creates a database backup."""
    from flask import current_app
    backup_dir = os.path.join(current_app.instance_path, 'backup', 'db')
    click.echo("Creating database backup...")
    success, result = BackupService.create_database_backup(backup_dir)
    if success:
        click.secho(f"Database backup created: {result}", fg='green')
    else:
        click.secho(f"Database backup failed: {result}", fg='red')
        raise click.ClickException(f"Database backup failed: {result}")

@db_group.command('restore')
@click.option('--file', '-f', help='Path to database backup file.')
@click.option('--latest', is_flag=True, help='Restore latest database backup.')
@click.option('--upgrade/--no-upgrade', default=True, help='Automatically run migrations after restore.')
@click.option('--stamp', help='Explicitly stamp to this version if restoring unversioned data.')
@with_appcontext
def db_restore(file, latest, upgrade, stamp):
    """Restores database from a backup."""
    from flask import current_app
    backup_dir = os.path.join(current_app.instance_path, 'backup', 'db')
    
    if latest:
        file = BackupService.get_latest_backup(backup_dir, 'backup_db_')
        
    if not file:
        click.secho("Error: Please specify --file or --latest", fg='red')
        raise click.ClickException("Error: Please specify --file or --latest")
        
    click.echo(f"Restoring database from {file}...")
    success, message = BackupService.restore_database(file, upgrade=upgrade, stamp_version=stamp)
    if success:
        click.secho(f"✅ {message}", fg='green')
    else:
        click.secho(f"❌ {message}", fg='red')
        raise click.ClickException(f"Database restore failed: {message}")


# --- System Command Group ---
@resources.group('system')
def system_group():
    """System resource backup operations (avatars, platform images, logos)."""
    pass

@system_group.command('backup')
@click.option('--increment', is_flag=True, help='Perform an incremental backup.')
@click.option('--full', is_flag=True, help='Perform a full backup (default).')
@with_appcontext
def system_backup(increment, full):
    """Creates a system resources backup."""
    from flask import current_app
    backup_dir = os.path.join(current_app.instance_path, 'backup', 'system')
    strategy = 'increment' if increment and not full else 'full'
    
    target_dirs = [
        'static/images',
        'static/uploads/avatars'
    ]
    
    click.echo(f"Creating system resources backup ({strategy})...")
    success, result = BackupService.create_file_backup(backup_dir, target_dirs, 'system', strategy=strategy)
    if success:
        if "skipped" in str(result).lower():
            click.secho(result, fg='yellow')
        else:
            click.secho(f"System backup completed: {result}", fg='green')
    else:
        click.secho(f"System backup failed: {result}", fg='red')
        raise click.ClickException(f"System backup failed: {result}")

@system_group.command('restore')
@click.option('--file', '-f', help='Path to system backup zip file.')
@click.option('--latest', is_flag=True, help='Restore latest system backup.')
@with_appcontext
def system_restore(file, latest):
    """Restores system resources from a backup."""
    from flask import current_app
    backup_dir = os.path.join(current_app.instance_path, 'backup', 'system')
    
    click.echo("Restoring system resources...")
    success, message = BackupService.restore_file_backup(backup_dir, target_file=file, latest=latest, resource_name='system')
    if success:
        click.secho(message, fg='green')
    else:
        click.secho(message, fg='red')
        raise click.ClickException(f"System restore failed: {message}")


# --- Club Command Group ---
@resources.group('club')
def club_group():
    """Club resource backup operations (club resources)."""
    pass

@club_group.command('backup')
@click.option('--increment', is_flag=True, help='Perform an incremental backup.')
@click.option('--full', is_flag=True, help='Perform a full backup (default).')
@with_appcontext
def club_backup(increment, full):
    """Creates a club resources backup."""
    from flask import current_app
    backup_dir = os.path.join(current_app.instance_path, 'backup', 'club')
    strategy = 'increment' if increment and not full else 'full'
    
    target_dirs = ['static/club_resources']
    
    click.echo(f"Creating club resources backup ({strategy})...")
    success, result = BackupService.create_file_backup(backup_dir, target_dirs, 'club', strategy=strategy)
    if success:
        if "skipped" in str(result).lower():
            click.secho(result, fg='yellow')
        else:
            click.secho(f"Club backup completed: {result}", fg='green')
    else:
        click.secho(f"Club backup failed: {result}", fg='red')
        raise click.ClickException(f"Club backup failed: {result}")

@club_group.command('restore')
@click.option('--file', '-f', help='Path to club backup zip file.')
@click.option('--latest', is_flag=True, help='Restore latest club backup.')
@with_appcontext
def club_restore(file, latest):
    """Restores club resources from a backup."""
    from flask import current_app
    backup_dir = os.path.join(current_app.instance_path, 'backup', 'club')
    
    click.echo("Restoring club resources...")
    success, message = BackupService.restore_file_backup(backup_dir, target_file=file, latest=latest, resource_name='club')
    if success:
        click.secho(message, fg='green')
    else:
        click.secho(message, fg='red')
        raise click.ClickException(f"Club restore failed: {message}")


# --- All Command Group ---
@resources.group('all')
def all_group():
    """All backups operations."""
    pass

@all_group.command('backup')
@click.option('--increment', is_flag=True, help='Perform incremental backup for files.')
@click.option('--full', is_flag=True, help='Perform full backup for files (default).')
@click.pass_context
def all_backup(ctx, increment, full):
    """Creates backups for db, system, and club."""
    click.echo("--- Starting database backup ---")
    ctx.invoke(db_backup)
    click.echo("--- Starting system resources backup ---")
    ctx.invoke(system_backup, increment=increment, full=full)
    click.echo("--- Starting club resources backup ---")
    ctx.invoke(club_backup, increment=increment, full=full)
    click.echo("✅ All backups completed.")

@all_group.command('restore')
@click.option('--latest', is_flag=True, help='Restore latest for all backups.')
@click.option('--db-file', help='Path to database backup file.')
@click.option('--system-file', help='Path to system backup zip file.')
@click.option('--club-file', help='Path to club backup zip file.')
@click.option('--upgrade/--no-upgrade', default=True, help='Automatically run migrations after db restore.')
@click.option('--stamp', help='Explicitly stamp to this version if restoring unversioned DB.')
@click.pass_context
def all_restore(ctx, latest, db_file, system_file, club_file, upgrade, stamp):
    """Restores db, system, and club resources."""
    if latest:
        click.echo("--- Restoring database (latest) ---")
        ctx.invoke(db_restore, latest=True, upgrade=upgrade, stamp=stamp)
        click.echo("--- Restoring system resources (latest) ---")
        ctx.invoke(system_restore, latest=True)
        click.echo("--- Restoring club resources (latest) ---")
        ctx.invoke(club_restore, latest=True)
    else:
        if db_file:
            click.echo(f"--- Restoring database ({db_file}) ---")
            ctx.invoke(db_restore, file=db_file, upgrade=upgrade, stamp=stamp)
        if system_file:
            click.echo(f"--- Restoring system resources ({system_file}) ---")
            ctx.invoke(system_restore, file=system_file)
        if club_file:
            click.echo(f"--- Restoring club resources ({club_file}) ---")
            ctx.invoke(club_restore, file=club_file)
            
        if not db_file and not system_file and not club_file:
            click.secho("Error: Please specify --latest or at least one of --db-file, --system-file, --club-file.", fg='red')
            raise click.ClickException("Error: Please specify --latest or at least one of --db-file, --system-file, --club-file.")

