# vpemaster/pathways_routes.py

from flask import Blueprint, render_template, request, jsonify, session
from vpemaster import db
from vpemaster.models import Project
from .main_routes import login_required

pathways_bp = Blueprint('pathways_bp', __name__)

@pathways_bp.route('/pathway_library')
def pathway_library():
    projects = Project.query.all()
    # Convert projects to a list of dictionaries to be easily used in JavaScript
    projects_data = [
        {
            "ID": p.ID,
            "Project_Name": p.Project_Name,
            "Introduction": p.Introduction,
            "Overview": p.Overview,
            "Purpose": p.Purpose,
            "Requirements": p.Requirements,
            "Resources": p.Resources,
            "Code_DL": p.Code_DL,
            "Code_EH": p.Code_EH,
            "Code_MS": p.Code_MS,
            "Code_PI": p.Code_PI,
            "Code_PM": p.Code_PM,
            "Code_VC": p.Code_VC,
            "Code_DTM": p.Code_DTM
        }
        for p in projects
    ]
    return render_template('pathway_library.html', projects=projects_data)


@pathways_bp.route('/pathway_library/update_project/<int:project_id>', methods=['POST'])
@login_required
def update_project(project_id):
    if session.get('user_role') != 'Admin':
        return jsonify(success=False, message="Permission denied"), 403

    project = Project.query.get_or_404(project_id)
    data = request.get_json()

    # Update project fields from the received JSON data
    project.Introduction = data.get('Introduction')
    project.Overview = data.get('Overview')
    project.Purpose = data.get('Purpose')
    project.Requirements = data.get('Requirements')
    project.Resources = data.get('Resources')

    db.session.commit()

    # Return a success response with the updated data
    return jsonify(
        success=True,
        Introduction=project.Introduction,
        Overview=project.Overview,
        Purpose=project.Purpose,
        Requirements=project.Requirements,
        Resources=project.Resources
    )

