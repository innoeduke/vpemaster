# vpemaster/speech_logs_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session
from vpemaster import db
from vpemaster.models import SpeechLog, Contact, User, Project
from .main_routes import login_required
from datetime import datetime

speech_logs_bp = Blueprint('speech_logs_bp', __name__)

@speech_logs_bp.route('/speech_logs')
@login_required
def show_speech_logs():
    user_role = session.get('user_role')
    all_logs = []

    if user_role == 'Member':
        user_id = session.get('user_id')
        if user_id:
            user = User.query.get(user_id)
            if user and user.Contact_ID:
                # If the user is a Member, only show their own speech logs
                all_logs = SpeechLog.query.filter_by(Contact_ID=user.Contact_ID).order_by(SpeechLog.Meeting_Number.asc()).all()
    else:
        # For Admins and Officers, show all speech logs
        all_logs = SpeechLog.query.order_by(SpeechLog.Meeting_Number.asc()).all()

    return render_template('speech_logs.html', logs=all_logs)

@speech_logs_bp.route('/speech_log/form', methods=['GET'])
@login_required
def speech_log_form():
    log_id = request.args.get('log_id', type=int)
    log = None
    if log_id:
        log = SpeechLog.query.get_or_404(log_id)

    members = Contact.query.filter_by(Type='Member').order_by(Contact.Name.asc()).all()
    projects = Project.query.all()
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
        }
        for p in projects
    ]

    return render_template('speech_log_form.html', log=log, members=members, projects=projects_data)

@speech_logs_bp.route('/speech_log/save/<int:log_id>', methods=['POST'])
@login_required
def save_speech_log(log_id):
    log = SpeechLog.query.get_or_404(log_id)
    contact_id = request.form.get('contact_id', type=int)
    contact = Contact.query.get(contact_id)

    log.Meeting_Number = request.form['meeting_number']
    log.Meeting_Date = datetime.strptime(request.form['meeting_date'], '%Y-%m-%d').date()
    log.Session = request.form['session']
    log.Speech_Title = request.form['speech_title']
    log.Pathway = request.form['pathway']
    log.Level = request.form['level']
    log.Name = contact.Name if contact else ''
    log.Contact_ID = contact.id if contact else 0
    log.Evaluator = request.form['evaluator']
    log.Project_Title = request.form['project_title']

    db.session.commit()
    return redirect(url_for('speech_logs_bp.show_speech_logs'))

@speech_logs_bp.route('/speech_log/add', methods=['POST'])
@login_required
def add_speech_log():
    contact_id = request.form.get('contact_id', type=int)
    contact = Contact.query.get(contact_id)

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
        Project_Title=request.form['project_title'],
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
    db.session.commit()
    return redirect(url_for('speech_logs_bp.show_speech_logs'))