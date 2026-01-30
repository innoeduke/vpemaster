# vpemaster/pathways_routes.py

from flask import Blueprint, render_template, request, jsonify, session
from . import db
from .models import Project, Pathway, PathwayProject, LevelRole
from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
from flask_login import current_user


pathways_bp = Blueprint('pathways_bp', __name__)


@pathways_bp.route('/pathway_library')
def pathway_library():
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
        
        # specific projects for this pathway from cache
        # sort by level then code? Original code didn't sort explicitly but relied on DB insertion order or default? 
        # Let's trust the order we appended or sort if needed. 
        # Usually level is important.
        
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
            
        ptype = pathway.type or "Other"
        if ptype not in grouped_pathways:
            grouped_pathways[ptype] = []
        grouped_pathways[ptype].append(pathway_dict)
        pathways_data.append(pathway_dict)

    return render_template('pathway_library.html', grouped_pathways=grouped_pathways, pathways=pathways_data) 


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

@pathways_bp.route('/path_progress')
@login_required
def path_progress():
    # Fetch all level roles
    level_roles = LevelRole.query.all()

    # Data structure:
    # rows: levels (sorted)
    # columns: bands (sorted)
    # cell data: list of roles

    # 1. Identify all unique bands and levels
    bands = set()
    levels = set()
    
    # 2. Group roles by (level, band)
    # matrix structure: { level_id: { band_id: [role_obj, ...], ... }, ... }
    matrix = {}

    for lr in level_roles:
        lvl = lr.level
        bnd = lr.band if lr.band is not None else 0 # Handle None band if any, though schema says nullable
        
        levels.add(lvl)
        bands.add(bnd)

        if lvl not in matrix:
            matrix[lvl] = {}
        
        if bnd not in matrix[lvl]:
            matrix[lvl][bnd] = []
            
        matrix[lvl][bnd].append(lr)

    # Convert sets to sorted lists
    sorted_levels = sorted(list(levels))
    sorted_bands = sorted(list(bands))

    # Prepare data for template
    # We want to iterate rows (levels) and then columns (bands)
    # data_rows = [ (level_id, [ (band_id, [roles]), ... ]), ... ]
    
    data_rows = []
    for lvl in sorted_levels:
        row_bands = []
        for bnd in sorted_bands:
            roles = matrix.get(lvl, {}).get(bnd, [])
            # Sort roles if needed, maybe by id or name
            roles.sort(key=lambda x: x.role) 
            row_bands.append({'band': bnd, 'roles': roles})
        data_rows.append({'level': lvl, 'bands': row_bands})

    return render_template('path_progress.html', 
                           bands=sorted_bands, 
                           data_rows=data_rows)
