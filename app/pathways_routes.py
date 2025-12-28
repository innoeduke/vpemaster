# vpemaster/pathways_routes.py

from flask import Blueprint, render_template, request, jsonify, session
from . import db
from .models import Project, Pathway, PathwayProject
from .auth.utils import login_required, is_authorized
from flask_login import current_user


pathways_bp = Blueprint('pathways_bp', __name__)


@pathways_bp.route('/pathway_library')
def pathway_library():
    pathways = Pathway.query.order_by(Pathway.name).all()
    
    # pre-fetch all pathway projects to create a lookup
    all_pp = db.session.query(PathwayProject, Pathway.abbr).join(Pathway).all()
    project_codes_lookup = {} # {project_id: {path_abbr: code, ...}}
    for pp, path_abbr in all_pp:
        if pp.project_id not in project_codes_lookup:
            project_codes_lookup[pp.project_id] = {}
        project_codes_lookup[pp.project_id][path_abbr] = pp.code

    # Group pathways by type
    grouped_pathways = {}
    pathways_data = []

    for pathway in pathways:
        pathway_dict = {
            'id': pathway.id,
            'name': pathway.name,
            'abbr': pathway.abbr,
            'type': pathway.type,
            'projects': []
        }
        
        # Get all project associations for this pathway
        pathway_projects = db.session.query(PathwayProject, Project).join(Project, PathwayProject.project_id == Project.id).filter(PathwayProject.path_id == pathway.id).all()

        for pathway_project, project in pathway_projects:
            project_dict = {
                "id": project.id,
                "Project_Name": project.Project_Name,
                "code": pathway_project.code,
                "type": pathway_project.type,
                "Introduction": project.Introduction or '',
                "Overview": project.Overview or '',
                "Purpose": project.Purpose or '',
                "Requirements": project.Requirements or '',
                "Resources": project.Resources or '',
                "path_codes": project_codes_lookup.get(project.id, {})
            }
            pathway_dict['projects'].append(project_dict)
            
        ptype = pathway.type or "Other"
        if ptype not in grouped_pathways:
            grouped_pathways[ptype] = []
        grouped_pathways[ptype].append(pathway_dict)
        pathways_data.append(pathway_dict)

    return render_template('pathway_library.html', grouped_pathways=grouped_pathways, pathways=pathways_data) 


@pathways_bp.route('/pathway_library/update_project/<int:project_id>', methods=['POST'])
@login_required
def update_project(project_id):
    if not is_authorized('PATHWAY_LIB_EDIT'):
        return jsonify(success=False, message="Permission denied"), 403

    project = Project.query.get_or_404(project_id)
    data = request.get_json()

    # Get and save raw text from the client
    project.Introduction = data.get('Introduction')
    project.Overview = data.get('Overview')
    project.Purpose = data.get('Purpose')
    project.Requirements = data.get('Requirements')
    project.Resources = data.get('Resources')

    db.session.commit()

    # Return raw text for display and re-editing
    return jsonify(
        success=True,
        Introduction=project.Introduction,
        Overview=project.Overview,
        Purpose=project.Purpose,
        Requirements=project.Requirements,
        Resources=project.Resources
    )
