import re
import argparse
from app import create_app, db
from app.models import Project

app = create_app()

def clean_resources(dry_run=False):
    with app.app_context():
        # Define patterns to clean
        # 1. "Evaluation Form: <url>"
        # 2. Links to specific domain "smsp-assets.oss-cn-shanghai.aliyuncs.com"
        
        domain = "smsp-assets.oss-cn-shanghai.aliyuncs.com"
        
        # Build query to find relevant projects
        # We look for "Evaluation Form:" OR the domain
        projects = Project.query.filter(
            (Project.Resources.like('%Evaluation Form:%')) | 
            (Project.Resources.like(f'%{domain}%'))
        ).all()
        
        print(f"Found {len(projects)} potential projects to clean.")

        count = 0
        for project in projects:
            original = project.Resources
            cleaned = original
            
            # --- Pattern 1: Domain specific cleanup ---
            # Construct a pattern that matches urls with the domain
            url_pattern = r'https?://[^\s\)]*' + re.escape(domain) + r'[^\s\)]*'
            
            # 1. Markdown link containing the domain: [Evaluation Form](...url...)
            cleaned = re.sub(r'\[.*?\]\(' + url_pattern + r'\)', '', cleaned, flags=re.IGNORECASE)
            
            # 2. "Evaluation Form" text followed by the URL
            cleaned = re.sub(r'Evaluation Form:?\s*' + url_pattern, '', cleaned, flags=re.IGNORECASE)
            
            # 3. Bare URL
            cleaned = re.sub(url_pattern, '', cleaned, flags=re.IGNORECASE)
            
            # --- Pattern 2: Generic "Evaluation Form: <url>" ---
            # This catches other domains too
            cleaned = re.sub(r'Evaluation Form:\s*https?://\S+', '', cleaned, flags=re.IGNORECASE)

            # --- Cleanup whitespace ---
            # Collapse multiple newlines
            cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
            cleaned = cleaned.strip()

            if original != cleaned:
                print(f"[{project.Project_Name}] Needs update.")
                # print(f"  Old: {original}")
                # print(f"  New: {cleaned}")
                
                if not dry_run:
                    project.Resources = cleaned
                    count += 1
            else:
                # This might happen if the query matched but regex didn't change anything (e.g. slight format diff)
                # or if one pattern cleaned it up and the other was redundant.
                pass

        if count > 0:
            if not dry_run:
                db.session.commit()
                print(f"Updated {count} projects.")
            else:
                print(f"Dry run: {count} projects would be updated.")
        else:
            print("No changes needed.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Clean up project resources.')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    args = parser.parse_args()
    
    clean_resources(dry_run=args.dry_run)
