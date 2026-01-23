import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import Permission

def check_categories():
    app = create_app()
    with app.app_context():
        perms = Permission.query.all()
        categories = {}
        for p in perms:
            cat = p.category
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(p.name)
            
        for cat, names in categories.items():
            print(f"Category: '{cat}'")
            for name in names:
                print(f"  - {name}")

if __name__ == "__main__":
    check_categories()
