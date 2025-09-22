# vpemaster/speech_logs_routes.py

from flask import Blueprint, jsonify, render_template, request, session
from vpemaster import db
from vpemaster.models import SessionLog, Contact, Project, Meeting, User
from .main_routes import login_required
from sqlalchemy import distinct, or_

speech_logs_bp = Blueprint('speech_logs_bp', __name__)

def _get_project_code(log):
    """Helper function to get the project code for a given log."""
    if not log or not log.project or not log.owner or not log.owner.Working_Path:
        return None

    pathway_to_code_attr = {
        "Dynamic Leadership": "Code_DL",
        "Engaging Humor": "Code_EH",
        "Motivational Strategies": "Code_MS",
        "Persuasive Influence": "Code_PI",
        "Presentation Mastery": "Code_PM",
        "Visionary Communication": "Code_VC",
    }
    code_attr = pathway_to_code_attr.get(log.owner.Working_Path)
    if not code_attr:
        return None

    return getattr(log.project, code_attr, None)


@speech_logs_bp.route('/speech_logs')
@login_required
def show_speech_logs():
    """
    Renders the page that displays pathway project speeches.
    - Admins/Officers can filter by any speaker.
    - Members can only see their own speeches.
    """
    user_role = session.get('user_role')
    is_member_view = (user_role == 'Member')

    selected_meeting = request.args.get('meeting_number')
    selected_pathway = request.args.get('pathway')
    selected_level = request.args.get('level')
    selected_speaker = request.args.get('speaker_id')

    # If the user is a Member, force the filter to their own Contact ID
    if is_member_view:
        user = User.query.get(session.get('user_id'))
        if user and user.Contact_ID:
            selected_speaker = user.Contact_ID
        else:
            # If member is not linked to a contact, show no logs by setting an invalid ID
            selected_speaker = -1

    query = db.session.query(SessionLog).join(Project)

    if selected_meeting:
        query = query.filter(SessionLog.Meeting_Number == selected_meeting)
    if selected_speaker:
        query = query.filter(SessionLog.Owner_ID == selected_speaker)

    initial_logs = query.order_by(SessionLog.Meeting_Number.desc()).all()

    grouped_logs = {}
    for log in initial_logs:
        if selected_pathway and (not log.owner or log.owner.Working_Path != selected_pathway):
            continue

        code = _get_project_code(log)
        if code:
            try:
                level = int(code.split('.')[0])
                if selected_level and level != int(selected_level):
                    continue

                if level not in grouped_logs:
                    grouped_logs[level] = []
                grouped_logs[level].append(log)
            except (ValueError, IndexError):
                continue

    sorted_grouped_logs = dict(sorted(grouped_logs.items()))

    meeting_numbers = sorted([m[0] for m in db.session.query(distinct(SessionLog.Meeting_Number)).join(Project).all()], reverse=True)
    speakers = db.session.query(Contact).join(SessionLog, Contact.id == SessionLog.Owner_ID).distinct().order_by(Contact.Name).all()
    pathways = [p[0] for p in db.session.query(distinct(Contact.Working_Path)).filter(Contact.Working_Path.isnot(None), ~Contact.Working_Path.like('Non-Path%')).order_by(Contact.Working_Path).all()]

    # Convert project objects to a list of dictionaries
    projects = Project.query.order_by(Project.Project_Name).all()
    projects_data = [
        {
            "ID": p.ID,
            "Project_Name": p.Project_Name,
            "Code_DL": p.Code_DL,
            "Code_EH": p.Code_EH,
            "Code_MS": p.Code_MS,
            "Code_PI": p.Code_PI,
            "Code_PM": p.Code_PM,
            "Code_VC": p.Code_VC
        }
        for p in projects
    ]

    return render_template(
        'speech_logs.html',
        grouped_logs=sorted_grouped_logs,
        get_project_code=_get_project_code,
        meeting_numbers=meeting_numbers,
        speakers=speakers,
        pathways=pathways,
        levels=range(1, 6),
        projects=projects_data,
        selected_filters={
            'meeting_number': selected_meeting,
            'pathway': selected_pathway,
            'level': selected_level,
            'speaker_id': selected_speaker
        },
        is_member_view=is_member_view
    )

@speech_logs_bp.route('/speech_log/details/<int:log_id>', methods=['GET'])
@login_required
def get_speech_log_details(log_id):
    """
    Fetches details for a specific speech log to populate the edit modal.
    """
    log = SessionLog.query.get_or_404(log_id)
    project_code = _get_project_code(log)
    level = int(project_code.split('.')[0]) if project_code else None

    log_data = {
        "id": log.id,
        "Session_Title": log.Session_Title,
        "Project_ID": log.Project_ID,
        "pathway": log.owner.Working_Path if log.owner else None,
        "level": level
    }

    return jsonify(success=True, log=log_data)


@speech_logs_bp.route('/speech_log/update/<int:log_id>', methods=['POST'])
@login_required
def update_speech_log(log_id):
    """
    Updates a speech log with new data from the edit modal.
    """
    log = SessionLog.query.get_or_404(log_id)
    data = request.get_json()

    if 'session_title' in data:
        log.Session_Title = data['session_title']

    if 'pathway' in data and log.owner:
        log.owner.Working_Path = data['pathway']

    if 'project_id' in data:
        log.Project_ID = data['project_id']

    try:
        db.session.commit()
        updated_project = Project.query.get(log.Project_ID)
        project_name = updated_project.Project_Name if updated_project else "N/A"
        project_code = _get_project_code(log)
        pathway = log.owner.Working_Path if log.owner else "N/A"

        return jsonify(success=True,
                       session_title=log.Session_Title,
                       project_name=project_name,
                       project_code=project_code,
                       pathway=pathway)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


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