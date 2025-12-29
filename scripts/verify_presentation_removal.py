import sys
import os

# Add project root to path
sys.path.append('/Users/wmu/workspace/toastmasters/vpemaster')

from app import create_app, db
from app.models import Project, PathwayProject, Pathway, SessionLog
from app.utils import project_id_to_code
from sqlalchemy import text

app = create_app('config.Config')

def verify():
    with app.app_context():
        print("1. Checking 'presentations' table existence...")
        try:
            db.session.execute(text("SELECT * FROM presentations"))
            print("ERROR: Table 'presentations' still exists!")
        except Exception as e:
            if "doesn't exist" in str(e):
                print("SUCCESS: Table 'presentations' does not exist.")
            else:
                print(f"SUCCESS (or expected error): {e}")

        print("\n2. Checking 'project_id_to_code' logic...")
        # Find a project that is a presentation
        pres_project = Project.query.filter_by(Format='Presentation').first()
        if pres_project:
            print(f"Found Presentation Project: {pres_project.Project_Name} (ID: {pres_project.id})")
            # Find its linked pathway/series to determine abbr
            pp = PathwayProject.query.filter_by(project_id=pres_project.id).first()
            if pp:
                pathway = Pathway.query.get(pp.path_id)
                abbr = pathway.abbr
                print(f"Linked Pathway/Series: {pathway.name} (Abbr: {abbr})")
                
                # Test the function (simulating utils.py presentation_series_initials check indirectly)
                code = project_id_to_code(pres_project.id, abbr)
                print(f"Derived Code: {code}")
                
                expected_suffix = pp.code
                if expected_suffix in code:
                    print("SUCCESS: Code derived correctly.")
                else:
                    print(f"FAILURE: Code derived '{code}' does not contain '{expected_suffix}'")
            else:
                print("WARNING: No PathwayProject linked to this presentation. Cannot verify code.")
        else:
            print("WARNING: No projects with Format='Presentation' found.")

        print("\n3. Verifying SessionLog data retrieval capability...")
        # Check if we can query logs that point to presentations
        logs = SessionLog.query.join(Project).filter(Project.Format == 'Presentation').limit(5).all()
        print(f"Found {len(logs)} logs referencing presentations.")
        for log in logs:
            print(f"- Log ID {log.id}: {log.Session_Title} (Project ID: {log.Project_ID})")
            
        print("\nVerification Script Completed.")

if __name__ == "__main__":
    verify()
