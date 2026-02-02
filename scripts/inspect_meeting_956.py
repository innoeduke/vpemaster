
import sys
import os

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.session import SessionLog, SessionType

def inspect_956():
    app = create_app()
    with app.app_context():
        logs = SessionLog.query.filter_by(Meeting_Number=956).all()
        print(f"--- Meeting 956 Logs ({len(logs)}) ---")
        for log in logs:
            st_title = log.session_type.Title if log.session_type else "None"
            print(f"ID: {log.id}, Title: '{log.Session_Title}', Type: '{st_title}', TypeID: {log.Type_ID}, Hidden: {log.hidden}")

if __name__ == "__main__":
    inspect_956()
