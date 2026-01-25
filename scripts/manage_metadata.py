import json
import os
import click
from flask.cli import with_appcontext
from app import db
from app.models import (
    LevelRole, Pathway, PathwayProject, Project, MeetingRole, 
    SessionType, Permission, AuthRole, RolePermission, Ticket
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
    Export all 10 metadata tables to JSON.
    """
    # Helper to get absolute path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_file = os.path.join(project_root, file)
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

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
        "tickets": [to_dict(t) for t in Ticket.query.all()]
    }
    
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

@metadata.command()
@click.option('--file', '-f', default='deploy/metadata_dump.json', help='Input JSON file path relative to project root')
@with_appcontext
def restore(file):
    """
    Restore metadata tables from JSON.
    This uses db.session.merge() to upsert records based on Primary Key.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    input_file = os.path.join(project_root, file)

    if not os.path.exists(input_file):
        click.echo(f"Error: File not found at {input_file}")
        return

    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Ensure tables exist
    db.create_all()

    # Map keys to Models
    model_map = {
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
    
    # Process in a specific order if necessary to handle foreign keys?
    # db.session.merge usually handles simple cases, but if we create new objects, 
    # dependent objects might need parents first.
    # The order in the backup dict is not guaranteed in older python, but here it's defined in code.
    # Let's define an explicit order for restoration to be safe.
    
    restore_order = [
         "meeting_roles", "pathways", "projects", "session_types", "permissions", "tickets", # Base tables
         "pathway_projects", "level_roles", "auth_roles", "role_permissions" # Dependent tables (roughly)
    ]
    
    # Ensure all keys in data are covered, even if not in restore_order (add them at the end)
    all_keys = list(data.keys())
    for k in all_keys:
        if k not in restore_order and k in model_map:
            restore_order.append(k)

    for table_name in restore_order:
        if table_name not in data:
            continue
            
        model = model_map.get(table_name)
        if not model:
            print(f"Warning: Unknown table {table_name} in dump file.")
            continue
            
        items = data[table_name]
        count = 0
        for item in items:
            # Create instance but don't add yet, we want to merge
            # We can't just pass dict to constructor blindly if there are relationships, 
            # but for metadata restoration, usually passing kwargs matches columns.
            # However, merge() expects an object.
            
            # We need to filter out keys that aren't columns (if any)
            # but to_dict only put columns in.
            
            # Note: merging requires the instance to have its PK set, which they should have from the dump.
            instance = model(**item)
            db.session.merge(instance)
            count += 1
        
        db.session.commit() # Commit after each table to ensure available for FKs
        total_records += count
        print(f"  ✓ {table_name:20s} - {count:4d} records merged")

    print(f"\nTotal: {total_records} metadata records processed")
