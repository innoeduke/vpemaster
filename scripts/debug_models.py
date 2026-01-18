import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import User, Message

app = create_app()
with app.app_context():
    print("Registered tables:")
    for table in db.metadata.tables:
        print(f"- {table}")
    
    print("\nUser table visible?", 'Users' in db.metadata.tables)
