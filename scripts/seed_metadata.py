import json
import os
import sys

# Add the parent directory to sys.path to allow importing app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import LevelRole, Pathway, PathwayProject, Project, Role, SessionType

# Define the order for insertion to respect foreign keys
ORDERED_MODELS = [
    ('roles', Role),
    ('pathways', Pathway),
    ('projects', Project),
    ('session_types', SessionType),
    ('pathway_projects', PathwayProject),
    ('level_roles', LevelRole)
]

def seed_metadata(dump_file='metadata_dump.json'):
    app = create_app()
    with app.app_context():
        # Clean slate: Drop all and create all
        print("Dropping all tables...")
        db.drop_all()
        print("Creating all tables...")
        db.create_all()
        
        # Load data
        dump_path = os.path.join(os.path.dirname(__file__), dump_file)
        if not os.path.exists(dump_path):
            print(f"Error: Dump file {dump_path} not found.")
            return

        with open(dump_path, 'r') as f:
            data = json.load(f)
            
        print("Seeding data...")
        try:
            for key, model_class in ORDERED_MODELS:
                if key in data:
                    items = data[key]
                    print(f"  - Seeding {len(items)} {key}...")
                    for item_data in items:
                        # Create instance
                        instance = model_class(**item_data)
                        db.session.add(instance)
                    
                    # Commit after each table to ensure IDs are available for FKs if needed
                    # (Though we are hardcoding the IDs from the dump, so they should match)
                    db.session.commit()
            
            print("Database seeded successfully!")
            
        except Exception as e:
            print(f"Error seeding database: {e}")
            db.session.rollback()

if __name__ == "__main__":
    seed_metadata()
