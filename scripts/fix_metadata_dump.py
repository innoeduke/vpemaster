import json
import os
import sys

# Define Global Club ID
GLOBAL_CLUB_ID = 1

def fix_metadata_dump():
    # Use absolute path relative to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dump_file_path = os.path.join(script_dir, '..', 'deploy', 'metadata_dump.json')
    
    if not os.path.exists(dump_file_path):
        print(f"Error: File not found at {dump_file_path}")
        return

    print(f"Loading {dump_file_path}...")
    with open(dump_file_path, 'r') as f:
        data = json.load(f)

    # 1. Fix Meeting Roles
    print("Processing meeting_roles...")
    roles = data.get('meeting_roles', [])
    cleaned_roles = []
    seen_roles = set() # (name, club_id) -> id
    
    # We want to consolidate "NULL" club_id roles into "CLUB 1" roles.
    # If a role exists for Club 1, keep it. If a role exists for NULL, move it to Club 1 (unless duplicate).
    
    # Dictionary to hold the canonical entry for each Name
    # Key: Role Name
    # Value: Role Dict
    canonical_roles = {}
    
    for role in roles:
        name = role.get('name')
        c_id = role.get('club_id')
        
        # We only care about Global (1) or NULL records for this fix.
        # Club-specific roles (id > 1) should be preserved as is? 
        # Wait, strictly speaking, the dump might simply have club_id: null for what should be 1.
        # But if there are other clubs in the dump, we shouldn't touch them.
        # Current understanding: This dump is the "Seed" metadata, mostly Global.
        
        if c_id not in [None, GLOBAL_CLUB_ID]:
            # Preserve other clubs' roles as is
            cleaned_roles.append(role)
            continue
            
        # For Global Candidates
        if name not in canonical_roles:
            role['club_id'] = GLOBAL_CLUB_ID
            canonical_roles[name] = role
        else:
            # Duplicate found
            # Prefer the one that already had club_id=1? Or just keep first?
            # Let's keep the one that "looks" better? No, just keep first.
            existing = canonical_roles[name]
            print(f" - Dedup: Dropping duplicate '{name}' (ID {role.get('id')}) in favor of ID {existing.get('id')}")
            pass
            
    # Add canonicals back
    cleaned_roles.extend(canonical_roles.values())
    data['meeting_roles'] = cleaned_roles
    print(f"Roles count: {len(roles)} -> {len(cleaned_roles)}")

    # 2. Fix Session Types
    print("Processing session_types...")
    types = data.get('session_types', [])
    cleaned_types = []
    canonical_types = {}
    
    for st in types:
        title = st.get('Title')
        c_id = st.get('club_id')
        
        if c_id not in [None, GLOBAL_CLUB_ID]:
            cleaned_types.append(st)
            continue
            
        if title not in canonical_types:
            st['club_id'] = GLOBAL_CLUB_ID
            canonical_types[title] = st
        else:
            existing = canonical_types[title]
            print(f" - Dedup: Dropping duplicate '{title}' (ID {st.get('id')}) in favor of ID {existing.get('id')}")

    cleaned_types.extend(canonical_types.values())
    data['session_types'] = cleaned_types
    print(f"Session Types count: {len(types)} -> {len(cleaned_types)}")

    # Save
    print(f"Saving to {dump_file_path}...")
    with open(dump_file_path, 'w') as f:
        json.dump(data, f, indent=4)
    print("Done.")

if __name__ == "__main__":
    fix_metadata_dump()
