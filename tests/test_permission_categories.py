import json
import os

def test_metadata_dump_permission_categories():
    """
    Verify that all contact-related permissions in deploy/metadata_dump.json
    share the exact same lowercase 'contacts' category.
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dump_path = os.path.join(project_root, 'deploy', 'metadata_dump.json')
    
    with open(dump_path, 'r') as f:
        data = json.load(f)
        
    permissions = data.get('permissions', [])
    contact_perms = [p for p in permissions if 'CONTACT' in p.get('name', '')]
    
    assert len(contact_perms) > 0, "No contact permissions found in metadata_dump.json"
    
    for p in contact_perms:
        name = p.get('name')
        category = p.get('category')
        assert category == 'contacts', f"Permission {name} has category '{category}', expected 'contacts'"
