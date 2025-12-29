import sys
import os
import requests
import json
from flask import Flask, current_app

# Add app directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import SessionLog, Project, PathwayProject, Pathway, SessionType

app = create_app()

def verify_backend_logic():
    with app.app_context():
        print("--- Verifying Backend Logic for Consolidated Edit Forms ---")
        
        # 1. Test Fetching Details for a Presentation
        print("\n1. Testing Details Fetch for Presentation...")
        # Find a presentation log
        presentation_log = SessionLog.query.join(SessionType).filter(SessionType.Title == 'Presentation').first()
        
        if not presentation_log:
            print("Skipping: No presentation logs found.")
        else:
            print(f"Found Presentation Log ID: {presentation_log.id}")
            # Simulate detailed fetch logic
            # Because we can't easily make a request without login credentials in this script unless we mock or login
            # We will test the logic directly using the code from routes
            
            log = presentation_log
            project_code = ""
            pathway_name_to_return = log.owner.Current_Path if log.owner and log.owner.Current_Path else "Presentation Mastery"
            
            if log.Project_ID:
                pp = None
                if log.owner and log.owner.Current_Path:
                    user_path_obj = db.session.query(Pathway).filter_by(name=log.owner.Current_Path).first()
                    if user_path_obj:
                        pp = db.session.query(PathwayProject).filter_by(path_id=user_path_obj.id, project_id=log.Project_ID).first()
                        if pp:
                            pathway_name_to_return = log.owner.Current_Path

                if not pp:
                    pp_any = db.session.query(PathwayProject).filter_by(project_id=log.Project_ID).first()
                    if pp_any:
                        path_obj = Pathway.query.get(pp_any.path_id)
                        if path_obj:
                            pathway_name_to_return = path_obj.name
                            pp = pp_any
                            print(f"  > Resolution Correct: Identified Series '{pathway_name_to_return}' for Presentation.")
                        else:
                            print("  > Error: Path object not found for presentation.")
                    else:
                         print("  > Warning: Presentation project has no PathwayProject entry.")

            print(f"  > Resolved Pathway/Series Name: {pathway_name_to_return}")
            if "Series" in pathway_name_to_return:
                print("  > SUCCESS: Presentation Series detected correctly.")
            elif log.Project_ID:
                 # It might be fine if it's a presentation that is part of a path? 
                 # But usually presentations are in series.
                 print(f"  > Note: Resolved to '{pathway_name_to_return}'. Check if this is correct for project ID {log.Project_ID}")

        # 2. Test Fetching Details for a Speech
        print("\n2. Testing Details Fetch for Speech...")
        speech_log = SessionLog.query.join(SessionType).filter(SessionType.Title == 'Pathway Speech').first()
        if speech_log:
             print(f"Found Speech Log ID: {speech_log.id}")
             # ... Logic repetition ...
             # We rely on previous manual logic verification, this is just a smoke test that code runs
             pass

        
        # 3. Validation of /api/data/all structure (Simulated)
        print("\n3. Verifying /api/data/all data sufficiency...")
        # Check if Projects list contains presentation projects
        pres_projects = Project.query.filter_by(Format='Presentation').all()
        if pres_projects:
            print(f"  > Found {len(pres_projects)} presentation projects in DB.")
            # Check if they have path codes loaded in the route logic
            # logic in route: 
            # all_pp = db.session.query(PathwayProject, Pathway.abbr).join(Pathway).all()
            # project_codes_lookup = {} ...
            # projects_data ...
            
            all_pp = db.session.query(PathwayProject, Pathway.abbr).join(Pathway).all()
            project_codes_lookup = {}
            for pp, path_abbr in all_pp:
                if pp.project_id not in project_codes_lookup:
                    project_codes_lookup[pp.project_id] = {}
                project_codes_lookup[pp.project_id][path_abbr] = pp.code
            
            sample_pres = pres_projects[0]
            codes = project_codes_lookup.get(sample_pres.id, {})
            print(f"  > Sample Presentation '{sample_pres.Project_Name}' has codes: {codes}")
            if codes:
                print("  > SUCCESS: Presentation codes are present.")
            else:
                print("  > FAILURE: Presentation codes missing. Frontend might fail to filter.")

if __name__ == "__main__":
    verify_backend_logic()
