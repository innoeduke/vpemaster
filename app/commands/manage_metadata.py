import json
import os
import click
from flask.cli import with_appcontext
from app import db
from app.constants import GLOBAL_CLUB_ID  # Import GLOBAL_CLUB_ID
from app.models import (
    LevelRole, Pathway, PathwayProject, Project, MeetingRole, 
    SessionType, Permission, AuthRole, RolePermission, Ticket, Club, ExComm
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
    
    Robust Merging: If a record with the same "natural key" (e.g. name) exists but 
    has a different ID, the ID is remapped to avoid IntegrityErrors.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    input_file = os.path.join(project_root, file)

    if not os.path.exists(input_file):
        click.echo(f"Error: File not found at {input_file}")
        return

    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Ensure tables and schema are up to date
    from flask import current_app
    if 'migrate' in current_app.extensions:
        import flask_migrate
        flask_migrate.upgrade()

    # Model configuration for robust merging
    # Natural Key: Columns that uniquely identify a record besides the Primary Key
    NATURAL_KEY_MAP = {
        Club: ['club_no'],
        Permission: ['name'],
        AuthRole: ['name'],
        Pathway: ['name'],
        Project: ['Project_Name'],
        MeetingRole: ['name', 'club_id'],
        SessionType: ['name', 'club_id'],
        Ticket: ['name'],
        LevelRole: ['level', 'role', 'type'],
        PathwayProject: ['path_id', 'project_id'],
        RolePermission: ['role_id', 'permission_id'],
        ExComm: ['club_id', 'year_start', 'year_end']
    }

    # Foreign Key Fields: Fields that need translation if the referenced record was remapped
    FK_FIELDS = {
        PathwayProject: {'path_id': Pathway, 'project_id': Project},
        RolePermission: {'role_id': AuthRole, 'permission_id': Permission},
        MeetingRole: {'club_id': Club},
        SessionType: {'club_id': Club},
        ExComm: {'club_id': Club},
        Club: {'current_excomm_id': ExComm}
    }

    # Map keys to Models
    model_map = {
        "clubs": Club,
        "excomm": ExComm,
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

    # ID Mapping: {Model: {old_id: new_id}}
    id_map = {m: {} for m in model_map.values()}

    print("=" * 70)
    print("METADATA RESTORE STARTED")
    print("=" * 70)

    total_records = 0
    restore_order = [
         "clubs", "excomm", "meeting_roles", "pathways", "projects", 
         "session_types", "permissions", "tickets", "pathway_projects", 
         "level_roles", "auth_roles", "role_permissions"
    ]
    
    # Add any extra tables found in dump but not explicit in order
    for k in data.keys():
        if k not in restore_order and k in model_map:
            restore_order.append(k)
            
    # Append clubs again for 2nd pass (to link excomm after excomm is restored)
    restore_order.append("clubs")

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
        
        is_clubs_pass_2 = (table_name == "clubs" and clubs_first_pass_done)
        
        if table_name == "clubs" and not clubs_first_pass_done:
            print(f"  > Processing {table_name} (Pass 1 - Unset ExComm)...")
        elif is_clubs_pass_2:
            print(f"  > Processing {table_name} (Pass 2 - Link ExComm)...")
        else:
            print(f"  > Processing {table_name}...")

        for item in items:
            old_id = item.get('id')
            
            # 1. Filter logic (Global only)
            if table_name in ["meeting_roles", "session_types"]:
                c_id = item.get('club_id')
                if c_id not in [GLOBAL_CLUB_ID, None]:
                    skipped += 1
                    continue

            # 2. Translate Foreign Keys using id_map
            remapped_item = item.copy()
            if model in FK_FIELDS:
                for field, referenced_model in FK_FIELDS[model].items():
                    val = remapped_item.get(field)
                    if val is not None and val in id_map[referenced_model]:
                        remapped_item[field] = id_map[referenced_model][val]

            # 3. Special handling for Pass 1 (Unset ExComm)
            if table_name == "clubs" and not clubs_first_pass_done:
                remapped_item['current_excomm_id'] = None
            
            # 4. robust Merging: Search for existing record by natural key
            if model in NATURAL_KEY_MAP:
                criteria = {col: remapped_item.get(col) for col in NATURAL_KEY_MAP[model]}
                # All criteria must be present for a meaningful search
                if all(v is not None or col in ['club_id'] for col, v in criteria.items()):
                    existing = model.query.filter_by(**criteria).first()
                    if existing:
                        remapped_item['id'] = existing.id
                        if old_id is not None:
                            id_map[model][old_id] = existing.id

            # 5. Merge
            instance = model(**remapped_item)
            merged = db.session.merge(instance)
            db.session.flush() # Ensure it's pushed to get ID if it was auto-inc (rare for metadata)
            
            # 6. Update id_map if it was a new record with a different ID
            if old_id is not None and old_id not in id_map[model]:
                id_map[model][old_id] = merged.id
                
            count += 1

        db.session.commit()
        if table_name == "clubs" and not clubs_first_pass_done:
            clubs_first_pass_done = True
        
        if not is_clubs_pass_2:
            total_records += count
            msg = f"  ✓ {table_name:20s} - {count:4d} records merged"
            if skipped > 0:
                msg += f" ({skipped} skipped - non-global)"
            print(msg)

    print(f"\nTotal: {total_records} metadata records processed")
