
import click
from flask.cli import with_appcontext
from app import db
from sqlalchemy import text

@click.command('cleanup-data')
@click.option('--force', is_flag=True, help='Skip confirmation prompt')
@with_appcontext
def cleanup_data(force):
    """
    Cleans up all data tables without dropping the database tables themselves.
    This effectively empties the database of all application data.
    """
    if not force:
        if not click.confirm("WARNING: This will delete ALL data from the database. Are you sure you want to continue?"):
            click.echo("Operation cancelled.")
            return

    click.echo("Starting data cleanup...")

    # Disable foreign key checks to allow deleting in any order (handles cycles too)
    # This syntax is slightly different for SQLite vs MySQL/Postgres.
    # Assuming MySQL or SQLite based on standard Flask setups.
    
    engine = db.engine
    dialect = engine.dialect.name

    try:
        if dialect == 'sqlite':
            db.session.execute(text("PRAGMA foreign_keys=OFF"))
        elif dialect == 'mysql':
            db.session.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        elif dialect == 'postgresql':
            db.session.execute(text("SET CONSTRAINTS ALL DEFERRED"))

        # Iterate over all tables and delete contents
        for table in reversed(db.metadata.sorted_tables):
            click.echo(f"Cleaning table: {table.name}")
            db.session.execute(table.delete())

        db.session.commit()
        click.echo("All data cleaned successfully.")

    except Exception as e:
        db.session.rollback()
        click.echo(f"Error cleaning data: {e}")
    finally:
        # Re-enable foreign key checks
        # Note: In a new transaction/connection usage, this might be redundant if the pool resets,
        # but safe to execute using db.session again.
        try:
            if dialect == 'sqlite':
                db.session.execute(text("PRAGMA foreign_keys=ON"))
            elif dialect == 'mysql':
                db.session.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            db.session.commit()
        except Exception:
            # Ignore errors during cleanup of settings, as main task is done or failed
            pass

