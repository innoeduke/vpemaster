#!/usr/bin/env python3
"""
Script to sync club and excomm settings from settings.ini to database.

Usage:
    python scripts/sync_club_settings.py
"""
import sys
import os

# Add parent directory to path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.utils import sync_club_from_settings, sync_excomm_from_settings


def main():
    """Main function to sync club and excomm settings."""
    app = create_app()
    
    with app.app_context():
        print("Syncing club settings from settings.ini...")
        club = sync_club_from_settings()
        
        if club:
            print(f"✓ Club synced successfully: {club.club_name} (ID: {club.id})")
            print(f"  - Club No: {club.club_no}")
            print(f"  - District: {club.district}")
            print(f"  - Meeting: {club.meeting_date} at {club.meeting_time}")
        else:
            print("✗ Failed to sync club settings. Check settings.ini [Club Settings] section.")
            return 1
        
        print("\nSyncing excomm team from settings.ini...")
        excomm = sync_excomm_from_settings()
        
        if excomm:
            print(f"✓ ExComm synced successfully: {excomm.excomm_name} ({excomm.excomm_term})")
            print(f"  Officers:")
            officers = excomm.get_officers()
            for role, contact in officers.items():
                if contact:
                    print(f"    - {role}: {contact.Name}")
                else:
                    print(f"    - {role}: (not assigned)")
        else:
            print("✗ Failed to sync excomm settings. Check settings.ini [Excomm Team] section.")
            return 1
        
        print("\n✓ All settings synced successfully!")
        return 0


if __name__ == '__main__':
    sys.exit(main())
