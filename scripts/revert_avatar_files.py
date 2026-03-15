
import os
import sys
import re
from datetime import datetime, timezone

# Add the project root to the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app

def revert_avatar_files(apply=False):
    app = create_app()
    with app.app_context():
        avatar_dir = os.path.join(app.root_path, 'static', app.config.get('AVATAR_ROOT_DIR', 'uploads/avatars'))
        
        if not os.path.exists(avatar_dir):
            print(f"Error: Directory {avatar_dir} does not exist.")
            return

        # Get all avatar files
        files = [f for f in os.listdir(avatar_dir) if re.match(r'avatar_\d+\.webp', f)]
        
        # Sort by ID ascending to avoid overwriting during rename (since we are shifting DOWN)
        files.sort(key=lambda x: int(re.search(r'\d+', x).group()), reverse=False)
        
        print(f"Analyzing {len(files)} files in {avatar_dir}...")
        
        today = datetime.now(timezone.utc).date()
        
        actions = []
        for f in files:
            file_path = os.path.join(avatar_dir, f)
            mtime = datetime.fromtimestamp(os.path.getmtime(file_path), tz=timezone.utc)
            
            # CRITICAL: Skip files updated today (like Alice's)
            if mtime.date() >= today:
                print(f"Skipping recently updated file: {f} (Modified: {mtime})")
                continue
                
            id_num = int(re.search(r'\d+', f).group())
            # We want to reverse: avatar_{n+1} -> avatar_{n}
            # Actually, we shifted EVERYTHING by +1. 
            # So if we have avatar_151.webp (and it was 150), we move it to 150.
            
            # Wait, if ID 110 had avatar_110.webp (Correct) and I moved it to avatar_111.webp.
            # Now I move it back to 110.
            
            new_filename = f"avatar_{id_num - 1}.webp"
            
            # Check if target already exists and is NEW
            target_path = os.path.join(avatar_dir, new_filename)
            if os.path.exists(target_path):
                target_mtime = datetime.fromtimestamp(os.path.getmtime(target_path), tz=timezone.utc)
                if target_mtime.date() >= today:
                    print(f"CONFLICT: Cannot rename {f} to {new_filename} because {new_filename} was updated today.")
                    continue

            actions.append((f, new_filename))

        if not apply:
            print("\n--- Proposed Reverts (Dry Run) ---")
            for old, new in actions:
                print(f"Revert: {old} -> {new}")
            print("\nDry run complete. Use --apply to perform reverts.")
            return

        print("\n--- Performing Reverts ---")
        moved = 0
        for old, new in actions:
            old_path = os.path.join(avatar_dir, old)
            new_path = os.path.join(avatar_dir, new)
            try:
                os.rename(old_path, new_path)
                print(f"SUCCESS: {old} -> {new}")
                moved += 1
            except Exception as e:
                print(f"FAILED: {old} -> {new} : {e}")
        
        print(f"\nMoved {moved} files.")

if __name__ == "__main__":
    apply = "--apply" in sys.argv
    revert_avatar_files(apply=apply)
