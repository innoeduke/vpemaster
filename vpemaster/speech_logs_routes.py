from flask import Blueprint, render_template, request, redirect, url_for, session
from vpemaster import db
from vpemaster.models import SpeechLog
from .main_routes import login_required
from datetime import datetime

speech_logs_bp = Blueprint('speech_logs_bp', __name__)

@speech_logs_bp.route('/speech_logs')
@login_required
def show_speech_logs():
    all_logs = SpeechLog.query.order_by(SpeechLog.Meeting_Number.asc()).all()
    return render_template('speech_logs.html', logs=all_logs)

@speech_logs_bp.route('/speech_log/form', methods=['GET'])
@login_required
def speech_log_form():
    log_id = request.args.get('log_id', type=int)
    log = None
    if log_id:
        log = SpeechLog.query.get_or_404(log_id)
    return render_template('speech_log_form.html', log=log)

@speech_logs_bp.route('/speech_log/save/<int:log_id>', methods=['POST'])
@login_required
def save_speech_log(log_id):
    log = SpeechLog.query.get_or_404(log_id)
    log.Meeting_Number = request.form['meeting_number']
    log.Meeting_Date = datetime.strptime(request.form['meeting_date'], '%Y-%m-%d').date()
    log.Session = request.form['session']
    log.Speech_Title = request.form['speech_title']
    log.Pathway = request.form['pathway']
    log.Level = request.form['level']
    log.Name = request.form['name']
    log.Evaluator = request.form['evaluator']
    log.Project_Title = request.form['project_title']
    log.Project_Type = request.form['project_type']
    log.Project_Status = request.form['project_status']

    db.session.commit()
    return redirect(url_for('speech_logs_bp.show_speech_logs'))

@speech_logs_bp.route('/speech_log/add', methods=['POST'])
@login_required
def add_speech_log():
    new_log = SpeechLog(
        Meeting_Number=request.form['meeting_number'],
        Meeting_Date=datetime.strptime(request.form['meeting_date'], '%Y-%m-%d').date(),
        Session=request.form['session'],
        Speech_Title=request.form['speech_title'],
        Pathway=request.form['pathway'],
        Level=request.form['level'],
        Name=request.form['name'],
        Evaluator=request.form['evaluator'],
        Project_Title=request.form['project_title'],
        Project_Type=request.form['project_type'],
        Project_Status=request.form['project_status']
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
