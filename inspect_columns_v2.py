import sys
import os
sys.path.append(os.getcwd())
try:
    from app import create_app, db
    from sqlalchemy import inspect
except ImportError as e:
    print(f"Import Error: {e}")
    sys.exit(1)

app = create_app()
with app.app_context():
    try:
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"Tables: {tables}")
        
        target_tables = ['owner_meeting_roles', 'Session_Logs']
        for table in target_tables:
            if table in tables:
                columns = inspector.get_columns(table)
                print(f"\nColumns in {table}:")
                for col in columns:
                    print(f" - {col['name']}")
            else:
                print(f"\nTable {table} not found!")
    except Exception as e:
        print(f"Error: {e}")
