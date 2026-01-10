import os
import json
import sys

# Add the parent directory to sys.path to allow importing app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Role, Pathway, Project, SessionType, PathwayProject, LevelRole

def seed_metadata(dump_file='instance/metadata_dump.json'):
    app = create_app()
    with app.app_context():
        # Load data
        dump_path = os.path.join(os.getcwd(), dump_file)
        if not os.path.exists(dump_path):
            # Try alternative path
            dump_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../instance/metadata_dump.json'))
            
        if not os.path.exists(dump_path):
            print(f"Error: Dump file {dump_path} not found.")
            return

        with open(dump_path, 'r') as f:
            data = json.load(f)
            
        print("Seeding data...")
        
        mapping = [
            (Role, 'roles'),
            (Pathway, 'pathways'),
            (Project, 'projects'),
            (SessionType, 'session_types'),
            (PathwayProject, 'pathway_projects'),
            (LevelRole, 'level_roles')
        ]
        
        try:
            for model_class, key in mapping:
                if key in data:
                    print(f"  - Checking {key}...")
                    items = data[key]
                    count = 0
                    for item_data in items:
                        # Only add if ID doesn't exist
                        if not model_class.query.get(item_data['id']):
                            instance = model_class(**item_data)
                            db.session.add(instance)
                            count += 1
                    db.session.commit()
                    print(f"    Added {count} new records.")
            
            print("Seeding completed successfully!")
            
        except Exception as e:
            print(f"Error seeding database: {e}")
            db.session.rollback()

if __name__ == "__main__":
    seed_metadata()
