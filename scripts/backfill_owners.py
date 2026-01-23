import sys
import os

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.session import SessionLog, session_log_owners
from sqlalchemy import insert

def backfill_session_log_owners():
    app = create_app()
    with app.app_context():
        print("Starting backfill of session_log_owners...")
        
        # Get all session logs that have an Owner_ID but no entries in session_log_owners
        logs = SessionLog.query.filter(SessionLog.Owner_ID.isnot(None)).all()
        
        count = 0
        for log in logs:
            # Check if an entry already exists for this log and its primary owner
            existing = db.session.query(session_log_owners).filter_by(
                session_log_id=log.id,
                contact_id=log.Owner_ID
            ).first()
            
            if not existing:
                # Insert entry into the association table
                stmt = insert(session_log_owners).values(
                    session_log_id=log.id,
                    contact_id=log.Owner_ID
                )
                db.session.execute(stmt)
                count += 1
        
        db.session.commit()
        print(f"Successfully backfilled {count} entries into session_log_owners.")

if __name__ == "__main__":
    backfill_session_log_owners()
