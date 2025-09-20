# vpemaster/speech_logs_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from vpemaster import db
from vpemaster.models import SpeechLog, Contact, User, Project, SessionLog
from .main_routes import login_required
from sqlalchemy import distinct
from datetime import datetime

speech_logs_bp = Blueprint('speech_logs_bp', __name__)

@speech_logs_bp.route('/speech_logs')
@login_required
def show_speech_logs():
    user_role = session.get('user_role')
    selected_owner = request.args.get('owner', '')
    selected_meeting = request.args.get('meeting_number', '')
    member_contact_data = None  # Initialize as None

    if not user_role:
        return redirect(url_for('agenda_bp.agenda'))

    query = SpeechLog.query
    owners = []
    meeting_numbers = []

    if user_role == 'Member':
        user_id = session.get('user_id')
        if user_id:
            user = User.query.get(user_id)
            if user and user.Contact_ID:
                query = query.filter_by(Contact_ID=user.Contact_ID)
                member_contact = Contact.query.get(user.Contact_ID)
                if member_contact:
                    # Convert the object to a JSON-serializable dictionary here.
                    member_contact_data = {
                        "id": member_contact.id,
                        "Working_Path": member_contact.Working_Path
                    }
    else:
        owner_names = db.session.query(distinct(SpeechLog.Name)).order_by(SpeechLog.Name.asc()).all()
        owners = [name[0] for name in owner_names]
        meeting_numbers_query = db.session.query(distinct(SpeechLog.Meeting_Number)).order_by(SpeechLog.Meeting_Number.desc()).all()
        meeting_numbers = [num[0] for num in meeting_numbers_query]

    if selected_owner:
        query = query.filter(SpeechLog.Name == selected_owner)
    if selected_meeting:
        query = query.filter(SpeechLog.Meeting_Number == selected_meeting)

    all_logs = query.order_by(SpeechLog.Meeting_Number.desc()).all()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('_speech_log_entries.html', logs=all_logs)

    members = Contact.query.filter_by(Type='Member').order_by(Contact.Name.asc()).all()
    projects = Project.query.all()
    projects_data = [
        {
            "ID": p.ID, "Project_Name": p.Project_Name, "Code_DL": p.Code_DL,
            "Code_EH": p.Code_EH, "Code_MS": p.Code_MS, "Code_PI": p.Code_PI,
            "Code_PM": p.Code_PM, "Code_VC": p.Code_VC,
        } for p in projects
    ]

    return render_template('speech_logs.html',
                           logs=all_logs,
                           owners=owners,
                           meeting_numbers=meeting_numbers,
                           selected_owner=selected_owner,
                           selected_meeting=selected_meeting,
                           members=members,
                           projects=projects_data,
                           member_contact=member_contact_data)


@speech_logs_bp.route('/speech_log/form', methods=['GET'])
@login_required
def speech_log_form():
    log_id = request.args.get('log_id', type=int)
    log = None
    project_id = None
    if log_id:
        log = SpeechLog.query.get_or_404(log_id)
        if session.get('user_role') == 'Member' and not log.Pathway:
            contact = Contact.query.get(log.Contact_ID)
            if contact and contact.Working_Path:
                log.Pathway = contact.Working_Path

        if log.Session_ID:
            session_log = SessionLog.query.get(log.Session_ID)
            if session_log: project_id = session_log.Project_ID
        elif log.Project_ID:
            project_id = log.Project_ID

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and log:
        log_data = {
            "Meeting_Number": log.Meeting_Number,
            "Meeting_Date": log.Meeting_Date.strftime('%Y-%m-%d') if log.Meeting_Date else '',
            "Contact_ID": log.Contact_ID, "Session": log.Session, "Pathway": log.Pathway,
            "Level": log.Level, "Speech_Title": log.Speech_Title, "Evaluator": log.Evaluator,
        }
        return jsonify(log=log_data, project_id=project_id)

    members = Contact.query.filter_by(Type='Member').order_by(Contact.Name.asc()).all()
    projects = Project.query.all()
    projects_data = [
        {
            "ID": p.ID, "Project_Name": p.Project_Name, "Code_DL": p.Code_DL,
            "Code_EH": p.Code_EH, "Code_MS": p.Code_MS, "Code_PI": p.Code_PI,
            "Code_PM": p.Code_PM, "Code_VC": p.Code_VC,
        } for p in projects
    ]
    return render_template('speech_log_form.html', log=log, members=members, projects=projects_data, project_id=project_id)

# ... (The rest of the file remains the same) ...
@speech_logs_bp.route('/speech_log/save/<int:log_id>', methods=['POST'])
@login_required
def save_speech_log(log_id):
    log = SpeechLog.query.get_or_404(log_id)
    contact_id = request.form.get('contact_id', type=int)
    contact = Contact.query.get(contact_id)
    project_id_str = request.form.get('project_id')
    project_id = int(project_id_str) if project_id_str and project_id_str.isdigit() else None
    project = Project.query.get(project_id) if project_id else None

    log.Meeting_Number = request.form['meeting_number']
    log.Meeting_Date = datetime.strptime(request.form['meeting_date'], '%Y-%m-%d').date()
    log.Session = request.form['session']
    log.Speech_Title = request.form['speech_title']
    log.Pathway = request.form['pathway']
    log.Level = request.form['level']
    log.Name = contact.Name if contact else ''
    log.Contact_ID = contact.id if contact else 0
    log.Evaluator = request.form['evaluator']
    log.Project_Title = project.Project_Name if project else ''
    log.Project_ID = project.ID if project else None

    if log.Session_ID:
        session_log = SessionLog.query.get(log.Session_ID)
        if session_log:
            session_log.Session_Title = log.Speech_Title
            session_log.Owner_ID = log.Contact_ID
            session_log.Project_ID = project.ID if project else None

    db.session.commit()
    return redirect(url_for('speech_logs_bp.show_speech_logs'))

@speech_logs_bp.route('/speech_log/add', methods=['POST'])
@login_required
def add_speech_log():
    contact_id = request.form.get('contact_id', type=int)
    contact = Contact.query.get(contact_id)
    project_id_str = request.form.get('project_id')
    project_id = int(project_id_str) if project_id_str and project_id_str.isdigit() else None
    project = Project.query.get(project_id) if project_id else None

    new_log = SpeechLog(
        Meeting_Number=request.form['meeting_number'],
        Meeting_Date=datetime.strptime(request.form['meeting_date'], '%Y-%m-%d').date(),
        Session=request.form['session'],
        Speech_Title=request.form['speech_title'],
        Pathway=request.form['pathway'],
        Level=request.form['level'],
        Name=contact.Name if contact else '',
        Contact_ID=contact.id if contact else 0,
        Evaluator=request.form['evaluator'],
        Project_Title=project.Project_Name if project else '',
        Project_ID=project.ID if project else None,
        Project_Status='Booked'
    )
    db.session.add(new_log)
    db.session.commit()
    return redirect(url_for('speech_logs_bp.show_speech_logs'))


@speech_logs_bp.route('/speech_log/delete/<int:log_id>', methods=['POST'])
@login_required
def delete_speech_log(log_id):
    log = SpeechLog.query.get_or_404(log_id)
    db.session.delete(log)
    db.session.commit()
    return redirect(url_for('speech_logs_bp.show_speech_logs'))

@speech_logs_bp.route('/speech_log/complete/<int:log_id>', methods=['POST'])
@login_required
def complete_speech_log(log_id):
    log = SpeechLog.query.get_or_404(log_id)
    log.Project_Status = 'Completed'
    try:
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500