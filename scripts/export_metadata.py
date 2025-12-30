import json
import os
import sys

# Add the parent directory to sys.path to allow importing app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import LevelRole, Pathway, PathwayProject, Project, Role, SessionType

def to_dict(model_instance):
    """Convert a SQLAlchemy model instance to a dictionary."""
    d = {}
    for column in model_instance.__table__.columns:
        d[column.name] = getattr(model_instance, column.name)
    return d

def export_metadata():
    app = create_app()
    with app.app_context():
        data = {
            "roles": [to_dict(r) for r in Role.query.all()],
            "pathways": [to_dict(p) for p in Pathway.query.all()],
            "projects": [to_dict(p) for p in Project.query.all()],
            "level_roles": [to_dict(l) for l in LevelRole.query.all()],
            "session_types": [to_dict(s) for s in SessionType.query.all()],
            "pathway_projects": [to_dict(pp) for pp in PathwayProject.query.all()]
        }
        
        output_file = os.path.join(os.path.dirname(__file__), 'metadata_dump.json')
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        print(f"Metadata exported successfully to {output_file}")
        print(f"Stats:")
        for table, items in data.items():
            print(f"  - {table}: {len(items)} records")

if __name__ == "__main__":
    export_metadata()
