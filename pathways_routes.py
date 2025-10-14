# vpemaster/pathways_routes.py

from flask import Blueprint, render_template, request, jsonify, session
from vpemaster import db
from vpemaster.models import Project
from .main_routes import login_required
import markdown

pathways_bp = Blueprint('pathways_bp', __name__)

def _render_markdown(text):
    """Renders raw Markdown text to HTML."""
    return markdown.markdown(text or '', extensions=['fenced_code'])

@pathways_bp.route('/pathway_library')
def pathway_library():
    projects = Project.query.all()
    # Convert projects to a list of dictionaries to be easily used in JavaScript
    projects_data = []
    for p in projects:
        raw_intro = p.Introduction or ''
        raw_overview = p.Overview or ''
        raw_purpose = p.Purpose or ''
        raw_requirements = p.Requirements or ''
        raw_resources = p.Resources or ''

        project_dict = {
            "ID": p.ID,
            "Project_Name": p.Project_Name,
            # Rendered HTML fields for display
            "Introduction": _render_markdown(raw_intro),
            "Overview": _render_markdown(raw_overview),
            "Purpose": _render_markdown(raw_purpose),
            "Requirements": _render_markdown(raw_requirements),
            "Resources": _render_markdown(raw_resources),
            # Raw Markdown fields for editing
            "Introduction_raw": raw_intro,
            "Overview_raw": raw_overview,
            "Purpose_raw": raw_purpose,
            "Requirements_raw": raw_requirements,
            "Resources_raw": raw_resources,
            "Code_DL": p.Code_DL,
            "Code_EH": p.Code_EH,
            "Code_MS": p.Code_MS,
            "Code_PI": p.Code_PI,
            "Code_PM": p.Code_PM,
            "Code_VC": p.Code_VC,
            "Code_DTM": p.Code_DTM
        }
        projects_data.append(project_dict)

    return render_template('pathway_library.html', projects=projects_data)


@pathways_bp.route('/pathway_library/update_project/<int:project_id>', methods=['POST'])
@login_required
def update_project(project_id):
    if session.get('user_role') != 'Admin':
        return jsonify(success=False, message="Permission denied"), 403

    project = Project.query.get_or_404(project_id)
    data = request.get_json()

    # Get and save raw markdown from the client
    raw_intro = data.get('Introduction')
    raw_overview = data.get('Overview')
    raw_purpose = data.get('Purpose')
    raw_requirements = data.get('Requirements')
    raw_resources = data.get('Resources')

    project.Introduction = raw_intro
    project.Overview = raw_overview
    project.Purpose = raw_purpose
    project.Requirements = raw_requirements
    project.Resources = raw_resources

    db.session.commit()

    # Return rendered HTML for display and raw Markdown for re-editing
    return jsonify(
        success=True,
        # Rendered HTML
        Introduction=_render_markdown(raw_intro),
        Overview=_render_markdown(raw_overview),
        Purpose=_render_markdown(raw_purpose),
        Requirements=_render_markdown(raw_requirements),
        Resources=_render_markdown(raw_resources),
        # Raw Markdown
        Introduction_raw=raw_intro,
        Overview_raw=raw_overview,
        Purpose_raw=raw_purpose,
        Requirements_raw=raw_requirements,
        Resources_raw=raw_resources,
    )