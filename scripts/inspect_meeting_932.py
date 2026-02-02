
import sys
import os

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.session import SessionLog

def inspect_932():
    app = create_app()
    with app.app_context():
        logs = SessionLog.query.filter_by(Meeting_Number=932).order_by(SessionLog.Meeting_Seq).all()
        print(f"--- Meeting 932 Logs ({len(logs)}) ---")
        for log in logs:
            owners = ", ".join([o.Name for o in log.owners])
            print(f"ID: {log.id}, Seq: {log.Meeting_Seq}, Time: {log.Start_Time}, Title: '{log.Session_Title}', Owners: [{owners}]")

if __name__ == "__main__":
    inspect_932()
