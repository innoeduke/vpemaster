import json
import os
import click
from flask.cli import with_appcontext
from app import db
from app.constants import GLOBAL_CLUB_ID  # Import GLOBAL_CLUB_ID
from app.models import (
    LevelRole, Pathway, PathwayProject, Project, MeetingRole, 
    SessionType, Permission, AuthRole, RolePermission, Ticket, Club, ExComm, ExcommOfficer
)

@click.group()
def metadata():
    """Manage metadata backup and restore."""
    pass

def to_dict(model_instance):
    """Convert a SQLAlchemy model instance to a dictionary."""
    d = {}
    if not model_instance:
        return d
    for column in model_instance.__table__.columns:
        d[column.name] = getattr(model_instance, column.name)
    return d

@metadata.command()
@click.option('--file', '-f', default='deploy/metadata_dump.json', help='Output JSON file path relative to project root')
@with_appcontext
def backup(file):
    """
    Export metadata tables to JSON.
    For MeetingRole and SessionType, EXCEPT ONLY Club 1 (Global) items.
    Now includes excomm table (but not officers).
    """
    # Helper to get absolute path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    output_file = os.path.join(project_root, file)
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Rotation: Move existing file to instance/backup if it exists
    if os.path.exists(output_file):
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d")
        
        # Define backup directory
        backup_dir = os.path.join(project_root, 'instance', 'backup')
        os.makedirs(backup_dir, exist_ok=True)

        # Get filename
        filename = os.path.basename(output_file)
        
        # Step 1: Move to instance/backup (keeping original name temporarily)
        dest_path = os.path.join(backup_dir, filename)
        
        try:
             # Move first
             os.rename(output_file, dest_path)
             
             # Step 2: Rename with timestamp
             base, ext = os.path.splitext(filename)
             rotated_filename = f"{base}_{timestamp}{ext}"
             rotated_file_path = os.path.join(backup_dir, rotated_filename)
             
             os.rename(dest_path, rotated_file_path)
             print(f"Moved existing backup to: {rotated_file_path}")
        except OSError as e:
             print(f"Warning: Failed to rotate backup file: {e}")

    # Filter for Global Club ID where applicable
    from sqlalchemy import or_

    data = {
        "clubs": [to_dict(c) for c in Club.query.all()],
        "excomm": [to_dict(e) for e in ExComm.query.all()],
        "excomm_officers": [to_dict(eo) for eo in ExcommOfficer.query.all()],
        "meeting_roles": [to_dict(r) for r in MeetingRole.query.filter(or_(MeetingRole.club_id == GLOBAL_CLUB_ID, MeetingRole.club_id.is_(None))).all()],
        "pathways": [to_dict(p) for p in Pathway.query.all()],
        "projects": [to_dict(p) for p in Project.query.all()],
        "level_roles": [to_dict(l) for l in LevelRole.query.all()],
        "session_types": [to_dict(s) for s in SessionType.query.filter(or_(SessionType.club_id == GLOBAL_CLUB_ID, SessionType.club_id.is_(None))).all()],
        "pathway_projects": [to_dict(pp) for pp in PathwayProject.query.all()],
        "permissions": [to_dict(p) for p in Permission.query.all()],
        "auth_roles": [to_dict(r) for r in AuthRole.query.all()],
        "role_permissions": [to_dict(rp) for rp in RolePermission.query.all()],
        "tickets": [to_dict(t) for t in Ticket.query.all()]
    }
    
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    print("=" * 70)
    print("METADATA EXPORT COMPLETE")
    print("=" * 70)
    print(f"Output file: {output_file}")
    print(f"\nExported metadata tables (filtered for Club {GLOBAL_CLUB_ID} where applicable):")
    total_records = 0
    for table, items in data.items():
        count = len(items)
        total_records += count
        print(f"  ✓ {table:20s} - {count:4d} records")
    print(f"\nTotal: {total_records} metadata records exported")

@metadata.command()
@click.option('--file', '-f', default='deploy/metadata_dump.json', help='Input JSON file path relative to project root')
@with_appcontext
def restore(file):
    """
    Restore metadata tables from JSON.
    This uses db.session.merge() to upsert records based on Primary Key.
    Discards MeetingRole and SessionType records not belonging to Club 1 (Global).
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    input_file = os.path.join(project_root, file)

    if not os.path.exists(input_file):
        click.echo(f"Error: File not found at {input_file}")
        return

    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Ensure tables and schema are up to date
    import flask_migrate
    flask_migrate.upgrade()

    # Map keys to Models
    model_map = {
        "clubs": Club,
        "excomm": ExComm,
        "excomm_officers": ExcommOfficer,
        "meeting_roles": MeetingRole,
        "pathways": Pathway,
        "projects": Project,
        "level_roles": LevelRole,
        "session_types": SessionType,
        "pathway_projects": PathwayProject,
        "permissions": Permission,
        "auth_roles": AuthRole,
        "role_permissions": RolePermission,
        "tickets": Ticket
    }

    print("=" * 70)
    print("METADATA RESTORE STARTED")
    print("=" * 70)

    total_records = 0
    
    # Restore Order
    # 1. Clubs (First pass, no Excomm linking)
    # 2. Base tables (Excomm is base relative to others, but depends on Club)
    # 3. Tables with dependencies
    # 4. Clubs (Second pass, link Excomm)
    
    restore_order = [
         "clubs", # Handled specially
         "excomm", # After clubs
         "meeting_roles", "pathways", "projects", "session_types", "permissions", "tickets", 
         "pathway_projects", "level_roles", "auth_roles", "role_permissions",
         "excomm_officers" # Depends on Excomm and Roles. Also Contacts (Business data?)
    ]
    
    # Add any extra tables found in dump but not explicit in order
    for k in data.keys():
        if k not in restore_order and k in model_map:
            restore_order.append(k)
            
    # Append clubs again for 2nd pass
    restore_order.append("clubs")

    # Track processing
    clubs_first_pass_done = False

    for table_name in restore_order:
        if table_name not in data:
            continue
            
        model = model_map.get(table_name)
        if not model:
             continue
             
        items = data[table_name]
        count = 0
        skipped = 0
        
        # Special handling for Clubs 2-pass restore
        if table_name == "clubs":
            if not clubs_first_pass_done:
                print(f"  > Processing {table_name} (Pass 1 - Unset ExComm)...")
                for item in items:
                    # Create copy and unset current_excomm_id to avoid FK issues
                    i = item.copy()
                    i['current_excomm_id'] = None
                    instance = model(**i)
                    db.session.merge(instance)
                    count += 1
                clubs_first_pass_done = True
            else:
                print(f"  > Processing {table_name} (Pass 2 - Link ExComm)...")
                for item in items:
                    # Only merge if it has excomm_id (optimization)
                    if item.get('current_excomm_id'):
                        instance = model(**item)
                        db.session.merge(instance)
                        count += 1
                # If no excomm links, count is 0, which is fine
        else:
            for item in items:
                # Filter logic: If restoring roles/types, discard if not Club 1 or None
                if table_name in ["meeting_roles", "session_types"]:
                    c_id = item.get('club_id')
                    if c_id not in [GLOBAL_CLUB_ID, None]:
                        skipped += 1
                        continue
                
                instance = model(**item)
                db.session.merge(instance)
                count += 1
        
        db.session.commit()
        if table_name != "clubs" or (table_name == "clubs" and clubs_first_pass_done):
             # Only add to total once or split logic? Just summation is fine.
             if table_name != "clubs":
                 total_records += count
                 
        msg = f"  ✓ {table_name:20s} - {count:4d} records merged"
        if skipped > 0:
            msg += f" ({skipped} skipped - non-global)"
        print(msg)

    print(f"\nTotal: {total_records} metadata records processed")
