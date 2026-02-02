"""
Export Metadata Tables Script

This script exports METADATA TABLES ONLY from the VPEMaster database.

DATABASE TABLE CATEGORIZATION:
===============================

METADATA TABLES (10 tables) - EXPORTED BY THIS SCRIPT:
-------------------------------------------------------
These tables contain reference data, configuration, and system definitions that:
- Are seeded during installation/migration
- Rarely change after initial setup
- Define system structure and rules
- Should be version-controlled as JSON dumps

1. meeting_roles - Meeting role definitions (Toastmaster, Timer, etc.)
2. pathways - Toastmasters pathway programs (Dynamic Leadership, etc.)
3. Projects - Toastmasters project definitions with details
4. pathway_projects - Junction table linking pathways to projects
5. level_roles - Required role counts per pathway level
6. Session_Types - Session/agenda item type definitions
7. permissions - System permission definitions for access control
8. auth_roles - User role definitions (SysAdmin, ClubAdmin, Staff, User)
9. role_permissions - Junction table mapping roles to permissions
10. tickets - Ticket definitions for events


BUSINESS DATA TABLES (15 tables) - NOT EXPORTED:
-------------------------------------------------
These tables contain operational data created during normal usage:
- Contacts, Users, user_roles
- clubs, excomm, contact_clubs
- Meetings, roster, roster_roles
- Session_Logs, waitlists, Media
- votes, achievements, permission_audits

These should be backed up regularly but NOT version-controlled as metadata.
"""

import json
import os
import sys

# Add the parent directory to sys.path to allow importing app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import (
    LevelRole, Pathway, PathwayProject, Project, MeetingRole, 
    SessionType, Permission, AuthRole, RolePermission, Ticket, Club, ExComm, ExcommOfficer
)
def to_dict(model_instance):
    """Convert a SQLAlchemy model instance to a dictionary."""
    d = {}
    if not model_instance:
        return d
    for column in model_instance.__table__.columns:
        d[column.name] = getattr(model_instance, column.name)
    return d

def export_metadata():
    """
    Export 11 metadata tables to JSON.
    
    This exports metadata tables including ExComm (but not officers).
    """
    app = create_app()
    with app.app_context():
        # Export all 11 metadata tables
        data = {
            "meeting_roles": [to_dict(r) for r in MeetingRole.query.all()],
            "pathways": [to_dict(p) for p in Pathway.query.all()],
            "projects": [to_dict(p) for p in Project.query.all()],
            "level_roles": [to_dict(l) for l in LevelRole.query.all()],
            "session_types": [to_dict(s) for s in SessionType.query.all()],
            "pathway_projects": [to_dict(pp) for pp in PathwayProject.query.all()],
            "permissions": [to_dict(p) for p in Permission.query.all()],
            "auth_roles": [to_dict(r) for r in AuthRole.query.all()],
            "role_permissions": [to_dict(rp) for rp in RolePermission.query.all()],
            "tickets": [to_dict(t) for t in Ticket.query.all()],
            "excomm": [to_dict(e) for e in ExComm.query.all()],
            "excomm_officers": [to_dict(eo) for eo in ExcommOfficer.query.all()]
        }
        
        output_file = os.path.join(os.path.dirname(__file__), 'metadata_dump.json')
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        print("=" * 70)
        print("METADATA EXPORT COMPLETE")
        print("=" * 70)
        print(f"Output file: {output_file}")
        print(f"\nExported 10 metadata tables:")
        total_records = 0
        for table, items in data.items():
            count = len(items)
            total_records += count
            print(f"  ✓ {table:20s} - {count:4d} records")
        print(f"\nTotal: {total_records} metadata records exported")
        print("\nNote: Business data tables (15 tables) are NOT exported.")
        print("      Use database backup tools for operational data.")

if __name__ == "__main__":
    export_metadata()
