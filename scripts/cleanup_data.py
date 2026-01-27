
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
            
            # Reset Autoincrement/Sequences
            try:
                if dialect == 'sqlite':
                    # SQLite stores sequences in sqlite_sequence table
                    db.session.execute(text("DELETE FROM sqlite_sequence WHERE name = :table_name"), {"table_name": table.name})
                elif dialect == 'mysql':
                    # MySQL resets usually with TRUNCATE or ALTER
                    # Since we are using DELETE, we need ALTER
                    db.session.execute(text(f"ALTER TABLE {table.name} AUTO_INCREMENT = 1"))
                elif dialect == 'postgresql':
                    # Postgres uses sequences. We can use TRUNCATE ... RESTART IDENTITY matches, 
                    # but here we used DELETE. So we need to reset the sequence.
                    # Getting the sequence name can be tricky, but usually table_id_seq.
                    # A safer way in PG is TRUNCATE table RESTART IDENTITY CASCADE, but we already deleted.
                    # Let's try to reset generic sequence if it adheres to standard naming,
                    # or use a PG specific command to reset all sequences?
                    # actually 'TRUNCATE table RESTART IDENTITY' is cleaner if we hadn't already deleted.
                    # But since we deleted, let's try:
                    # db.session.execute(text(f"ALTER SEQUENCE {table.name}_id_seq RESTART WITH 1"))
                    # Note: This assumes standard naming and that the 'id' column uses a sequence.
                    pass
            except Exception as e:
                # Some tables might not have sequences (e.g. association tables), ignore
                # print(f"    (Note: Could not reset sequence for {table.name}: {e})")
                pass

        # Global sequence reset for SQLite (cleaner than per-table sometimes, but per-table is fine)
        # if dialect == 'sqlite':
        #    db.session.execute(text("DELETE FROM sqlite_sequence"))

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

