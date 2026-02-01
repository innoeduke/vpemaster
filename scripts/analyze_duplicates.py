import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import SessionType, MeetingRole
from sqlalchemy import func

def analyze_duplicates():
    app = create_app()
    with app.app_context():
        print("Analyzing Role Duplicates (club_id=NULL)...")
        
        # Check for roles with club_id=NULL
        null_roles = MeetingRole.query.filter(MeetingRole.club_id.is_(None)).all()
        print(f"Total roles with club_id=NULL: {len(null_roles)}")
        
        # Group by name
        role_counts = {}
        for r in null_roles:
            role_counts[r.name] = role_counts.get(r.name, []) + [r]
            
        duplicates = {k: v for k, v in role_counts.items() if len(v) > 1}
        print(f"Found {len(duplicates)} duplicated role names:")
        for name, instances in duplicates.items():
            print(f" - '{name}': {[r.id for r in instances]}")

        print("\nAnalyzing SessionType Duplicates (club_id=NULL)...")
        null_types = SessionType.query.filter(SessionType.club_id.is_(None)).all()
        print(f"Total session types with club_id=NULL: {len(null_types)}")
        
        type_counts = {}
        for t in null_types:
            type_counts[t.Title] = type_counts.get(t.Title, []) + [t]
            
        dup_types = {k: v for k, v in type_counts.items() if len(v) > 1}
        print(f"Found {len(dup_types)} duplicated session type titles:")
        for title, instances in dup_types.items():
            print(f" - '{title}': {[t.id for t in instances]}")

if __name__ == "__main__":
    analyze_duplicates()
