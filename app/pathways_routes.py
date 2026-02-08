# vpemaster/pathways_routes.py

from flask import Blueprint, render_template, request, jsonify, session
from . import db
from .models import Project, Pathway, PathwayProject, LevelRole
from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
from flask_login import current_user


pathways_bp = Blueprint('pathways_bp', __name__)


def get_pathway_library_data():
    pathways = Pathway.query.filter_by(status='active').order_by(Pathway.name).all()
    
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

    # Fetch all project associations for ALL pathways in one go
    # Join Project to get details
    all_pathway_projects = db.session.query(PathwayProject, Project)\
        .join(Project, PathwayProject.project_id == Project.id)\
        .all()

    # Group by path_id in memory
    pp_by_path = {}
    for pp, proj in all_pathway_projects:
        if pp.path_id not in pp_by_path:
            pp_by_path[pp.path_id] = []
        pp_by_path[pp.path_id].append((pp, proj))

    for pathway in pathways:
        pathway_dict = {
            'id': pathway.id,
            'name': pathway.name,
            'abbr': pathway.abbr,
            'type': pathway.type,
            'projects': []
        }
        
        projs = pp_by_path.get(pathway.id, [])
        # Optional: Sort by level for better display
        projs.sort(key=lambda x: (x[0].level if x[0].level else 99, x[0].code))

        for pathway_project, project in projs:
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
                "path_codes": project_codes_lookup.get(project.id, {}),
                "level": pathway_project.level
            }
            pathway_dict['projects'].append(project_dict)
            
        ptype = pathway.type
        if ptype and ptype.lower() != 'others':
            label = ptype.upper()
            if label not in grouped_pathways:
                grouped_pathways[label] = []
            grouped_pathways[label].append(pathway_dict)
            pathways_data.append(pathway_dict)

    # Sort grouped_pathways by keys (labels) ascending
    grouped_pathways = dict(sorted(grouped_pathways.items()))
    
    return {
        'grouped_pathways': grouped_pathways,
        'pathways': pathways_data
    }

@pathways_bp.route('/pathway_library')
def pathway_library():
    if not is_authorized(Permissions.PATHWAY_LIB_VIEW):
        return redirect(url_for('agenda_bp.agenda'))

    has_lucky_draw_access = is_authorized(Permissions.LUCKY_DRAW_VIEW)
    has_pathways_access = is_authorized(Permissions.PATHWAY_LIB_VIEW)
    
    data = get_pathway_library_data()
    return render_template(
        'pathway_library.html', 
        **data,
        active_tab='pathway_library',
        has_lucky_draw_access=has_lucky_draw_access,
        has_pathways_access=has_pathways_access,
        Permissions=Permissions
    )


@pathways_bp.route('/pathway_library/update_project/<int:project_id>', methods=['POST'])
@login_required
def update_project(project_id):
    if not is_authorized(Permissions.PATHWAY_LIB_EDIT):
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


