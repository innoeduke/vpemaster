# vpemaster/speech_logs_routes.py

from flask import Blueprint, jsonify
from vpemaster import db
from vpemaster.models import SessionLog, Contact, Project
from .main_routes import login_required

speech_logs_bp = Blueprint('speech_logs_bp', __name__)

def _get_next_project_for_contact(contact, completed_log):
    if not contact or not contact.Working_Path or not completed_log or not completed_log.Project_ID:
        return

    pathway_to_code_attr = {
        "Dynamic Leadership": "Code_DL",
        "Engaging Humor": "Code_EH",
        "Motivational Strategies": "Code_MS",
        "Persuasive Influence": "Code_PI",
        "Presentation Mastery": "Code_PM",
        "Visionary Communication": "Code_VC",
    }
    code_attr = pathway_to_code_attr.get(contact.Working_Path)
    if not code_attr:
        return

    completed_project = Project.query.get(completed_log.Project_ID)
    if not completed_project:
        return
    current_code = getattr(completed_project, code_attr)

    if not current_code:
        return

    try:
        level, project_num = map(int, current_code.split('.'))
        next_project_num = project_num + 1
        next_project = Project.query.filter(getattr(Project, code_attr) == f"{level}.{next_project_num}").first()

        if next_project:
            contact.Next_Project = f"{level}.{next_project_num}"
        else:
            contact.Next_Project = f"{level + 1}.1"
    except (ValueError, IndexError):
        return

@speech_logs_bp.route('/speech_log/complete/<int:log_id>', methods=['POST'])
@login_required
def complete_speech_log(log_id):
    log = SessionLog.query.get_or_404(log_id)
    log.Status = 'Completed'

    if log.Owner_ID:
        contact = Contact.query.get(log.Owner_ID)
        _get_next_project_for_contact(contact, log)

    try:
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500