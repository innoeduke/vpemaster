# innoeduke/vpemaster/vpemaster-dev0.3/speech_logs_routes.py
from flask import Blueprint, jsonify, render_template, request, session, current_app
from vpemaster import db
from vpemaster.models import SessionLog, Contact, Project, User
from .main_routes import login_required
from sqlalchemy import distinct
import re

speech_logs_bp = Blueprint('speech_logs_bp', __name__)

def _get_project_code(log):
    """Helper function to get the project code for a given log."""
    if not log or not log.project or not log.owner or not log.owner.Working_Path:
        return None

    pathway_to_code_attr = current_app.config['PATHWAY_MAPPING']
    code_prefix = pathway_to_code_attr.get(log.owner.Working_Path)
    if not code_prefix:
        return None

    return getattr(log.project, f"Code_{code_prefix}", None)


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
    selected_status = request.args.get('status')

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
    if selected_status:
        query = query.filter(SessionLog.Status == selected_status)

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

    # Sort logs within each level group by project code
    for level in grouped_logs:
        grouped_logs[level].sort(key=lambda log: _get_project_code(log) or "")

    sorted_grouped_logs = dict(sorted(grouped_logs.items()))

    meeting_numbers = sorted([m[0] for m in db.session.query(distinct(SessionLog.Meeting_Number)).join(Project).all()], reverse=True)
    speakers = db.session.query(Contact).join(SessionLog, Contact.id == SessionLog.Owner_ID).distinct().order_by(Contact.Name).all()

    # Updated logic to get pathways from the app config
    pathways = list(current_app.config['PATHWAY_MAPPING'].keys())

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
            "Code_VC": p.Code_VC,
            "Code_DTM": p.Code_DTM
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
            'speaker_id': selected_speaker,
            'status': selected_status
        },
        is_member_view=is_member_view,
        pathway_mapping=current_app.config['PATHWAY_MAPPING']
    )

@speech_logs_bp.route('/speech_log/details/<int:log_id>', methods=['GET'])
@login_required
def get_speech_log_details(log_id):
    """
    Fetches details for a specific speech log to populate the edit modal.
    """
    log = SessionLog.query.get_or_404(log_id)
    project_code = _get_project_code(log)
    level = int(project_code.split('.')[0]) if project_code else 1

    pathway = log.owner.Working_Path if log.owner and log.owner.Working_Path else "Presentation Mastery"

    log_data = {
        "id": log.id,
        "Session_Title": log.Session_Title,
        "Project_ID": log.Project_ID,
        "pathway": pathway,
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
        owner = Contact.query.get(log.Owner_ID)
        if owner:
            owner.Working_Path = data['pathway']
            db.session.add(owner)

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
                       pathway=pathway,
                       project_id=log.Project_ID)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500

@speech_logs_bp.route('/speech_log/suspend/<int:log_id>', methods=['POST'])
@login_required
def suspend_speech_log(log_id):
    if session.get('user_role') not in ['Admin', 'VPE']:
        return jsonify(success=False, message="Permission denied"), 403

    log = SessionLog.query.get_or_404(log_id)
    log.Status = 'Delivered'
    try:
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


def _get_next_project_for_contact(contact, completed_log):
    if not contact or not contact.Working_Path or not completed_log or not completed_log.Project_ID:
        return

    pathway_to_code_attr = current_app.config['PATHWAY_MAPPING']
    code_suffix = pathway_to_code_attr.get(contact.Working_Path)
    if not code_suffix:
        return

    completed_project = Project.query.get(completed_log.Project_ID)
    if not completed_project:
        return
    current_code = getattr(completed_project, f"Code_{code_suffix}")

    if not current_code:
        return

    projects_per_level = {1: 3, 2: 3, 3: 3, 4: 2, 5: 3}

    try:
        level, project_num = map(int, current_code.split('.'))

        # Get all completed project IDs for this user in this pathway
        completed_project_ids = [
            log.Project_ID for log in SessionLog.query
            .join(Contact, SessionLog.Owner_ID == Contact.id)
            .filter(Contact.id == contact.id, Contact.Working_Path == contact.Working_Path, SessionLog.Status == 'Completed')
            .all()
        ]

        while True:
            if project_num < projects_per_level.get(level, 0):
                project_num += 1
            else:
                project_num = 1
                level_completed = level
                level += 1

                # Smart update for Completed_Levels
                completed_pathways = {}
                if contact.Completed_Levels:
                    parts = contact.Completed_Levels.split('/')
                    for part in parts:
                        match = re.match(r"([A-Z]+)(\d+)", part)
                        if match:
                            path, l = match.groups()
                            completed_pathways[path] = int(l)

                completed_pathways[code_suffix] = level_completed

                new_completed_levels = [f"{path}{lvl}" for path, lvl in sorted(completed_pathways.items())]
                contact.Completed_Levels = "/".join(new_completed_levels)


            if level > 5:
                contact.Next_Project = None
                break

            next_project_code = f"{level}.{project_num}"
            next_project = Project.query.filter(getattr(Project, f"Code_{code_suffix}") == next_project_code).first()

            if next_project and next_project.ID not in completed_project_ids:
                contact.Next_Project = f"{code_suffix}{next_project_code}"
                break
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