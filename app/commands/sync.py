import os
import time
import click
from flask.cli import with_appcontext
from app.services.backup_service import BackupService

def get_connection_details(ctx):
    from flask import current_app
    user = ctx.obj.get('user') or current_app.config.get('SYNC_REMOTE_USER') or 'ubuntu'
    host = ctx.obj.get('host') or current_app.config.get('SYNC_REMOTE_HOST') or 'moleqode.com'
    path = ctx.obj.get('path') or current_app.config.get('SYNC_REMOTE_BASE_PATH') or '/var/www/vpemaster/instance/backup'
    return user, host, path

def run_sync_with_fallback(ctx, resource_name):
    user, host, path = get_connection_details(ctx)
    
    # Try passwordless first
    click.echo(f"🔌 Checking passwordless SSH connection to {user}@{host}...")
    success, msg = BackupService.sync_remote_backup(resource_name, user, host, path)
    if success:
        return True, None
        
    # If it failed, fallback to interactive username/password prompting
    click.secho(f"⚠️ Passwordless connection failed: {msg}", fg='yellow')
    click.echo("🔄 Falling back to interactive username and password authentication.")
    
    prompt_user = click.prompt("Remote SSH username", default=user)
    password = click.prompt("Remote SSH password", hide_input=True)
    
    success, msg = BackupService.sync_remote_backup(resource_name, prompt_user, host, path, password=password)
    if success:
        return True, prompt_user
    else:
        click.secho(f"❌ Error: Sync failed: {msg}", fg='red')
        raise click.ClickException(f"Sync failed: {msg}")

@click.group('sync', invoke_without_command=True)
@click.option('--user', help='Remote SSH username.')
@click.option('--host', help='Remote SSH host.')
@click.option('--path', help='Remote base directory containing backups.')
@click.pass_context
def sync(ctx, user, host, path):
    """Sync backup data from remote server and restore locally."""
    ctx.ensure_object(dict)
    ctx.obj['user'] = user
    ctx.obj['host'] = host
    ctx.obj['path'] = path
    
    if ctx.invoked_subcommand is None:
        # Default to invoking 'all' subcommand when just "flask sync" is called
        ctx.invoke(sync_all)

@sync.command('db')
@click.pass_context
@with_appcontext
def sync_db(ctx):
    """Sync database backups and restore locally."""
    run_sync_with_fallback(ctx, 'db')
    
    # Post-pull
    from flask import current_app
    backup_dir = os.path.join(current_app.instance_path, 'backup', 'db')
    latest_file = BackupService.get_latest_backup(backup_dir, 'backup_db_')
    if not latest_file:
        click.secho("Error: No database backup file found to restore.", fg='red')
        raise click.ClickException("No database backup file found.")
        
    click.echo("🔄 Restoring database...")
    success, message = BackupService.restore_database(latest_file, upgrade=True)
    if not success:
        click.secho(f"❌ Database restore failed: {message}", fg='red')
        raise click.ClickException(f"Database restore failed: {message}")
    click.secho(f"✅ {message}", fg='green')
    
    # Run data migrations
    click.echo("🛠️ Running data migrations...")
    BackupService.migrate_contact_pathways()
    BackupService.migrate_owner_meeting_roles()
    click.secho("✅ Data migrations complete.", fg='green')

@sync.command('system')
@click.pass_context
@with_appcontext
def sync_system(ctx):
    """Sync system resources backups."""
    run_sync_with_fallback(ctx, 'system')

@sync.command('club')
@click.pass_context
@with_appcontext
def sync_club(ctx):
    """Sync club resources backups."""
    run_sync_with_fallback(ctx, 'club')

@sync.command('all')
@click.pass_context
@with_appcontext
def sync_all(ctx):
    """Sync db, system, and club backups, and restore database."""
    user, host, path = get_connection_details(ctx)
    
    password = None
    prompt_user = user
    
    # Try passwordless connection to db first
    click.echo(f"🔌 Checking passwordless SSH connection to {user}@{host}...")
    success, msg = BackupService.sync_remote_backup('db', user, host, path)
    if not success:
        click.secho(f"⚠️ Passwordless connection failed: {msg}", fg='yellow')
        click.echo("🔄 Falling back to interactive username and password authentication.")
        prompt_user = click.prompt("Remote SSH username", default=user)
        password = click.prompt("Remote SSH password", hide_input=True)
        
        # Re-run db sync with password
        success, msg = BackupService.sync_remote_backup('db', prompt_user, host, path, password=password)
        if not success:
            click.secho(f"❌ Error: DB sync failed: {msg}", fg='red')
            raise click.ClickException(f"DB sync failed: {msg}")
    
    # Sync system backups
    time.sleep(1.5)
    click.echo("🔍 Syncing system resources backups...")
    success, msg = BackupService.sync_remote_backup('system', prompt_user, host, path, password=password)
    if not success:
        click.secho(f"❌ Error: System sync failed: {msg}", fg='red')
        raise click.ClickException(f"System sync failed: {msg}")
        
    # Sync club backups
    time.sleep(1.5)
    click.echo("🔍 Syncing club resources backups...")
    success, msg = BackupService.sync_remote_backup('club', prompt_user, host, path, password=password)
    if not success:
        click.secho(f"❌ Error: Club sync failed: {msg}", fg='red')
        raise click.ClickException(f"Club sync failed: {msg}")
        
    # Post-pull
    from flask import current_app
    backup_dir = os.path.join(current_app.instance_path, 'backup', 'db')
    latest_file = BackupService.get_latest_backup(backup_dir, 'backup_db_')
    if not latest_file:
        click.secho("Error: No database backup file found to restore.", fg='red')
        raise click.ClickException("No database backup file found.")
        
    click.echo("🔄 Restoring database...")
    success, message = BackupService.restore_database(latest_file, upgrade=True)
    if not success:
        click.secho(f"❌ Database restore failed: {message}", fg='red')
        raise click.ClickException(f"Database restore failed: {message}")
    click.secho(f"✅ {message}", fg='green')
    
    # Run data migrations
    click.echo("🛠️ Running data migrations...")
    BackupService.migrate_contact_pathways()
    BackupService.migrate_owner_meeting_roles()
    click.secho("✅ Data migrations complete.", fg='green')
