#!/usr/bin/env python3
"""
Populate first_name and last_name fields for all contacts based on the Name column.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import create_app, db
from app.models import Contact

def populate_names():
    """Split Name into first_name and last_name for all contacts."""
    app = create_app()
    
    with app.app_context():
        contacts = Contact.query.all()
        updated_count = 0
        skipped_count = 0
        
        for contact in contacts:
            # Skip if already populated
            if contact.first_name and contact.last_name:
                skipped_count += 1
                continue
            
            if not contact.Name:
                print(f"Warning: Contact ID {contact.id} has no Name")
                skipped_count += 1
                continue
            
            # Split the name
            name_parts = contact.Name.strip().split(None, 1)  # Split on first whitespace
            
            if len(name_parts) == 1:
                # Single name - use as first name
                contact.first_name = name_parts[0]
                contact.last_name = ''
            else:
                # Multiple parts - first is first_name, rest is last_name
                contact.first_name = name_parts[0]
                contact.last_name = name_parts[1]
            
            updated_count += 1
            print(f"Updated: {contact.Name} -> first_name='{contact.first_name}', last_name='{contact.last_name}'")
        
        # Commit all changes
        db.session.commit()
        
        print(f"\n✓ Successfully updated {updated_count} contacts")
        print(f"  Skipped {skipped_count} contacts (already populated or no name)")
        print(f"  Total contacts: {len(contacts)}")

if __name__ == '__main__':
    populate_names()
