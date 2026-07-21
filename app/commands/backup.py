import os
import click
from flask.cli import with_appcontext
from ..services.backup_service import BackupService

TYPE_CHOICES = click.Choice(['db', 'system', 'club', 'all'], case_sensitive=False)


@click.group('resources')
@click.option('--type', '-t', 'group_type', type=TYPE_CHOICES, default=None, help='Resource type to operate on (db, system, club, all).')
@click.pass_context
def resources(ctx, group_type):
    """Database and resource backup management."""
    ctx.ensure_object(dict)
    if isinstance(ctx.obj, dict):
        ctx.obj['type'] = group_type
    ctx.group_type = group_type


def _get_res_type(ctx, cmd_type):
    group_type = getattr(ctx, 'group_type', None)
    if not group_type and isinstance(ctx.obj, dict):
        group_type = ctx.obj.get('type')
    return (cmd_type or group_type or 'all').lower()


def _do_db_backup():
    from flask import current_app
    backup_dir = os.path.join(current_app.instance_path, 'backup', 'db')
    click.echo("Creating database backup...")
    success, result = BackupService.create_database_backup(backup_dir)
    if success:
        click.secho(f"Database backup created: {result}", fg='green')
    else:
        click.secho(f"Database backup failed: {result}", fg='red')
        raise click.ClickException(f"Database backup failed: {result}")


def _do_system_backup(increment, full):
    from flask import current_app
    backup_dir = os.path.join(current_app.instance_path, 'backup', 'system')
    strategy = 'increment' if increment and not full else 'full'
    
    target_dirs = [
        'static/images',
        'static/avatars'
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


def _do_club_backup(increment, full):
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


@resources.command('backup')
@click.option('--type', '-t', type=TYPE_CHOICES, default=None, help='Resource type to backup (db, system, club, all).')
@click.option('--increment', is_flag=True, help='Perform an incremental backup for file resources.')
@click.option('--full', is_flag=True, help='Perform a full backup for file resources (default).')
@click.pass_context
@with_appcontext
def backup(ctx, type, increment, full):
    """Creates a backup for database, system, club, or all resources."""
    res_type = _get_res_type(ctx, type)
    if res_type == 'db':
        _do_db_backup()
    elif res_type == 'system':
        _do_system_backup(increment, full)
    elif res_type == 'club':
        _do_club_backup(increment, full)
    elif res_type == 'all':
        click.echo("--- Starting database backup ---")
        _do_db_backup()
        click.echo("--- Starting system resources backup ---")
        _do_system_backup(increment, full)
        click.echo("--- Starting club resources backup ---")
        _do_club_backup(increment, full)
        click.echo("✅ All backups completed.")


def _do_db_restore(file, latest, upgrade, stamp):
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


def _do_system_restore(file, latest):
    from flask import current_app
    backup_dir = os.path.join(current_app.instance_path, 'backup', 'system')
    
    if not file and not latest:
        click.secho("Error: Please specify --file or --latest", fg='red')
        raise click.ClickException("Error: Please specify --file or --latest")
        
    click.echo("Restoring system resources...")
    success, message = BackupService.restore_file_backup(backup_dir, target_file=file, latest=latest, resource_name='system')
    if success:
        click.secho(message, fg='green')
    else:
        click.secho(message, fg='red')
        raise click.ClickException(f"System restore failed: {message}")


def _do_club_restore(file, latest):
    from flask import current_app
    backup_dir = os.path.join(current_app.instance_path, 'backup', 'club')
    
    if not file and not latest:
        click.secho("Error: Please specify --file or --latest", fg='red')
        raise click.ClickException("Error: Please specify --file or --latest")
        
    click.echo("Restoring club resources...")
    success, message = BackupService.restore_file_backup(backup_dir, target_file=file, latest=latest, resource_name='club')
    if success:
        click.secho(message, fg='green')
    else:
        click.secho(message, fg='red')
        raise click.ClickException(f"Club restore failed: {message}")


@resources.command('restore')
@click.option('--type', '-t', type=TYPE_CHOICES, default=None, help='Resource type to restore (db, system, club, all).')
@click.option('--file', '-f', help='Path to backup file.')
@click.option('--latest', is_flag=True, help='Restore latest backup.')
@click.option('--upgrade/--no-upgrade', default=True, help='Automatically run migrations after db restore.')
@click.option('--stamp', help='Explicitly stamp to this version if restoring unversioned DB.')
@click.option('--db-file', help='Path to database backup file (when type is all).')
@click.option('--system-file', help='Path to system backup zip file (when type is all).')
@click.option('--club-file', help='Path to club backup zip file (when type is all).')
@click.pass_context
@with_appcontext
def restore(ctx, type, file, latest, upgrade, stamp, db_file, system_file, club_file):
    """Restores database, system, club, or all resources from a backup."""
    res_type = _get_res_type(ctx, type)
    
    if res_type == 'db':
        target_file = file or db_file
        _do_db_restore(target_file, latest, upgrade, stamp)
    elif res_type == 'system':
        target_file = file or system_file
        _do_system_restore(target_file, latest)
    elif res_type == 'club':
        target_file = file or club_file
        _do_club_restore(target_file, latest)
    elif res_type == 'all':
        if latest:
            click.echo("--- Restoring database (latest) ---")
            _do_db_restore(db_file or (file if not system_file and not club_file else None), latest=True, upgrade=upgrade, stamp=stamp)
            click.echo("--- Restoring system resources (latest) ---")
            _do_system_restore(system_file, latest=True)
            click.echo("--- Restoring club resources (latest) ---")
            _do_club_restore(club_file, latest=True)
        else:
            eff_db = db_file or file
            eff_sys = system_file
            eff_club = club_file
            
            if not eff_db and not eff_sys and not eff_club:
                click.secho("Error: Please specify --latest or at least one of --db-file, --system-file, --club-file.", fg='red')
                raise click.ClickException("Error: Please specify --latest or at least one of --db-file, --system-file, --club-file.")
            
            if eff_db:
                click.echo(f"--- Restoring database ({eff_db}) ---")
                _do_db_restore(eff_db, latest=False, upgrade=upgrade, stamp=stamp)
            if eff_sys:
                click.echo(f"--- Restoring system resources ({eff_sys}) ---")
                _do_system_restore(eff_sys, latest=False)
            if eff_club:
                click.echo(f"--- Restoring club resources ({eff_club}) ---")
                _do_club_restore(eff_club, latest=False)
