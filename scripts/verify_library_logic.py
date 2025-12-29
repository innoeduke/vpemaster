import sys
import os

# Add project root to path
sys.path.append('/Users/wmu/workspace/toastmasters/vpemaster')

from app import create_app, db
from app.models import Project, Pathway, PathwayProject
from flask import json

app = create_app('config.Config')

def verify_library_logic():
    with app.app_context():
        # 1. Simulate the fetch logic from pathways_routes.py
        pathways = Pathway.query.all()
        
        # Identify a presentation pathway
        pres_pathway = Pathway.query.filter(Pathway.type == 'Presentation').first()
        if not pres_pathway:
            # Fallback if no specific 'Presentation' type, look for known series
            pres_pathway = Pathway.query.filter(Pathway.name.like('%Series%')).first()
            
        if pres_pathway:
            print(f"Testing Pathway: {pres_pathway.name} (ID: {pres_pathway.id})")
            
            pathway_projects = db.session.query(PathwayProject, Project).join(
                Project, PathwayProject.project_id == Project.id
            ).filter(PathwayProject.path_id == pres_pathway.id).all()
            
            print(f"Found {len(pathway_projects)} projects.")
            
            levels_found = set()
            for pp, proj in pathway_projects:
                print(f" - Project: {proj.Project_Name}, Level: {pp.level}, Code: {pp.code}")
                levels_found.add(pp.level)
                
            print(f"Unique Levels: {sorted(list(levels_found))}")
            
            if len(levels_found) > 0:
                print("SUCCESS: Pathway projects have levels associated.")
            else:
                print("WARNING: No levels found for this pathway.")
        else:
            print("WARNING: No Presentation pathway found to test.")

if __name__ == "__main__":
    verify_library_logic()
