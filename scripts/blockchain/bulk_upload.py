import os
import sys
from dotenv import load_dotenv
from flask import Flask

# Add the project root to the path so we can import the app module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app import create_app, db
from app.models.achievement import Achievement
from app.blockchain import record_level_completion_on_chain
import time

def upload_existing_achievements():
    """
    Finds all valid 'level-completion' achievements in the database
    and records them to the Sepolia blockchain.
    """
    print("Initializing Flask app context...")
    app = create_app()
    
    with app.app_context():
        # Query all level completions
        completions = Achievement.query.filter_by(achievement_type='level-completion').all()
        
        valid_completions = [
            c for c in completions 
            if c.path_name and c.level and c.member_id
        ]
        
        total = len(valid_completions)
        print(f"Found {len(completions)} level completions in total.")
        print(f"Found {total} VALID level completions (with member_id, path_name, and level).")
        print("-" * 50)
        
        if total == 0:
            print("No valid achievements to upload.")
            return

        confirm = input(f"Do you want to upload these {total} records to Sepolia? (y/n): ")
        if confirm.lower() != 'y':
            print("Operation cancelled.")
            return
            
        success_count = 0
        failure_count = 0

        for i, c in enumerate(valid_completions, 1):
            print(f"[{i}/{total}] Uploading: Member {c.member_id} | Path '{c.path_name}' | Level {c.level}")
            
            try:
                # We reuse the utility method already built for the app
                success = record_level_completion_on_chain(c.member_id, c.path_name, c.level)
                
                if success:
                    success_count += 1
                else:
                    failure_count += 1
                    
            except Exception as e:
                print(f"Error uploading record {i}: {e}")
                failure_count += 1
                
            # Sleep briefly to avoid spamming the RPC endpoint too hard
            time.sleep(0.5)
            
        print("-" * 50)
        print("Upload complete!")
        print(f"Successfully sent transaction for {success_count} records.")
        if failure_count > 0:
            print(f"Failed to upload {failure_count} records.")

if __name__ == "__main__":
    # Load environment variables just to ensure they are available
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '..', '.env'))
    
    # Verify environment has keys
    if not os.getenv("SEPOLIA_RPC_URL") or not os.getenv("WALLET_PRIVATE_KEY") or not os.getenv("LEVEL_TRACKER_CONTRACT_ADDRESS"):
        print("Error: Missing one of (SEPOLIA_RPC_URL, WALLET_PRIVATE_KEY, LEVEL_TRACKER_CONTRACT_ADDRESS) in .env")
        sys.exit(1)
        
    upload_existing_achievements()
