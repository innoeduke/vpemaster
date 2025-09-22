# vpemaster/agenda_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, send_file
from .main_routes import login_required
from .models import SessionLog, SessionType, Contact, Meeting, Project
from vpemaster import db
from sqlalchemy import distinct
from datetime import datetime, timedelta
import io
import csv
import re

agenda_bp = Blueprint('agenda_bp', __name__)

# --- Helper Functions for Data Fetching ---

def _get_agenda_logs(meeting_number):
    """Fetches all agenda logs and related data for a specific meeting."""
    query = db.session.query(
        SessionLog,
        SessionType.Is_Section,
        SessionType.Title.label('session_type_title'),
        SessionType.Is_Titleless,
        Meeting.Meeting_Date,
        Project.Code_DL, Project.Code_EH, Project.Code_MS,
        Project.Code_PI, Project.Code_PM, Project.Code_VC
    ).join(SessionType, SessionLog.Type_ID == SessionType.id, isouter=True)\
     .join(Meeting, Meeting.Meeting_Number == SessionLog.Meeting_Number)\
     .outerjoin(Project, SessionLog.Project_ID == Project.ID)

    if meeting_number:
        query = query.filter(SessionLog.Meeting_Number == meeting_number)

    return query.order_by(SessionLog.Meeting_Seq.asc()).all()

def _get_project_speakers(meeting_number):
    """Gets a list of speakers for a given meeting."""
    if not meeting_number:
        return []
    speaker_logs = db.session.query(Contact.Name)\
        .join(SessionLog, Contact.id == SessionLog.Owner_ID)\
        .join(SessionType, SessionLog.Type_ID == SessionType.id)\
        .filter(
            SessionLog.Meeting_Number == meeting_number,
            SessionType.Valid_for_Project == True
        ).all()
    return [name[0] for name in speaker_logs]

def _create_or_update_session(item, meeting_number, seq):
    meeting = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
    if not meeting:
        new_meeting = Meeting(Meeting_Number=meeting_number)
        db.session.add(new_meeting)
        db.session.flush()
        meeting = new_meeting

    type_id = item.get('type_id')
    if type_id == '':
        type_id = None

    session_title = item.get('session_title')
    project_id = item.get('project_id') if item.get('project_id') else None
    status = item.get('status') if item.get('status') else 'Booked'

    if item['id'] == 'new':
        new_log = SessionLog(
            Meeting_Number=meeting_number,
            Meeting_Seq=seq,
            Type_ID=type_id,
            Owner_ID=item['owner_id'] if item['owner_id'] else None,
            Duration_Min=item['duration_min'] if item['duration_min'] else None,
            Duration_Max=item['duration_max'] if item['duration_max'] else None,
            Project_ID=project_id,
            Session_Title=session_title,
            Status=status
        )
        db.session.add(new_log)
    else:
        log = SessionLog.query.get(item['id'])
        if log:
            log.Meeting_Number = meeting_number
            log.Meeting_Seq = seq
            log.Type_ID = type_id
            log.Owner_ID = item.get('owner_id') if item.get('owner_id') else None
            log.Duration_Min = item.get('duration_min') if item.get('duration_min') else None
            log.Duration_Max = item.get('duration_max') if item.get('duration_max') else None
            log.Project_ID = project_id
            log.Status = status
            if session_title is not None:
                log.Session_Title = session_title

def _recalculate_start_times(meeting_numbers_to_update):
    for meeting_num in meeting_numbers_to_update:
        meeting = Meeting.query.filter_by(Meeting_Number=meeting_num).first()
        if not meeting or not meeting.Start_Time:
            continue

        current_time = meeting.Start_Time
        logs_to_update = db.session.query(SessionLog, SessionType.Is_Section)\
            .join(SessionType, SessionLog.Type_ID == SessionType.id, isouter=True)\
            .filter(SessionLog.Meeting_Number == meeting_num)\
            .order_by(SessionLog.Meeting_Seq.asc()).all()

        for log, is_section in logs_to_update:
            if not is_section:
                log.Start_Time = current_time
                duration_to_add = int(log.Duration_Max or 0)
                break_minutes = 1
                if log.Session_Title and log.Session_Title.startswith('Evaluation'):
                    break_minutes += 1
                dt_current_time = datetime.combine(datetime.today(), current_time)
                next_dt = dt_current_time + timedelta(minutes=duration_to_add + break_minutes)
                current_time = next_dt.time()
            else:
                log.Start_Time = None

# --- Main Route ---

@agenda_bp.route('/agenda', methods=['GET'])
def agenda():
    meeting_numbers_query = db.session.query(distinct(SessionLog.Meeting_Number)).order_by(SessionLog.Meeting_Number.desc()).all()
    meeting_numbers = [num[0] for num in meeting_numbers_query]

    selected_meeting_str = request.args.get('meeting_number')
    selected_meeting = int(selected_meeting_str) if selected_meeting_str else (meeting_numbers[0] if meeting_numbers else None)

    session_logs = _get_agenda_logs(selected_meeting)
    project_speakers = _get_project_speakers(selected_meeting)

    # Data for templates and JavaScript
    projects = Project.query.order_by(Project.Project_Name).all()
    projects_data = [
        {
            "ID": p.ID, "Project_Name": p.Project_Name, "Code_DL": p.Code_DL,
            "Code_EH": p.Code_EH, "Code_MS": p.Code_MS, "Code_PI": p.Code_PI,
            "Code_PM": p.Code_PM, "Code_VC": p.Code_VC
        } for p in projects
    ]
    pathways = [p[0] for p in db.session.query(distinct(Contact.Working_Path)).filter(Contact.Working_Path.isnot(None), ~Contact.Working_Path.like('Non-Path%')).order_by(Contact.Working_Path).all()]
    session_types = SessionType.query.order_by(SessionType.Title.asc()).all()
    session_types_data = [{"id": s.id, "Title": s.Title, "Is_Section": s.Is_Section, "Valid_for_Project": s.Valid_for_Project} for s in session_types]
    contacts = Contact.query.order_by(Contact.Name.asc()).all()
    contacts_data = [
        {
            "id": c.id, "Name": c.Name, "DTM": c.DTM, "Type": c.Type,
            "Club": c.Club, "Working_Path": c.Working_Path, "Next_Project": c.Next_Project,
            "Completed_Levels": c.Completed_Levels
        } for c in contacts
    ]
    members = Contact.query.filter_by(Type='Member').order_by(Contact.Name.asc()).all()

    return render_template('agenda.html',
                           logs=session_logs,
                           session_types=session_types_data,
                           contacts=contacts,
                           contacts_data=contacts_data,
                           projects=projects_data,
                           pathways=pathways,
                           meeting_numbers=meeting_numbers,
                           selected_meeting=selected_meeting,
                           members=members,
                           project_speakers=project_speakers)

# --- Other Routes ---
# (The rest of the file remains the same)

@agenda_bp.route('/agenda/load', methods=['POST'])
@login_required
def load_csv():
    if 'file' not in request.files:
        return redirect(url_for('agenda_bp.agenda', message='No file part', category='error'))

    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('agenda_bp.agenda', message='No selected file', category='error'))

    if file and file.filename.endswith('.csv'):
        file_content = file.stream.read()
        try:
            decoded_content = file_content.decode('utf-8')
        except UnicodeDecodeError:
            decoded_content = file_content.decode('gbk', errors='replace')

        stream = io.StringIO(decoded_content, newline=None)
        first_line = stream.readline().strip()
        cleaned_line = re.sub(r'^\W+|\W+$', '', first_line)
        parts = cleaned_line.split(',')
        if len(parts) < 2:
            return redirect(url_for('agenda_bp.agenda', message='Invalid first line format.', category='error'))

        meeting_number, start_time_str = parts[0], parts[1]

        try:
            current_time = datetime.strptime(start_time_str, '%H:%M').time()
        except ValueError:
            return redirect(url_for('agenda_bp.agenda', message='Invalid start time format in first line.', category='error'))

        meeting = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
        if not meeting:
            meeting = Meeting(Meeting_Number=meeting_number, Start_Time=current_time)
            db.session.add(meeting)
        else:
            meeting.Start_Time = current_time
        db.session.commit()

        csv_reader = csv.reader(stream)
        seq = 1
        for row in csv_reader:
            if not row: continue
            session_title_from_csv = row[0].strip() if len(row) > 0 else ''
            owner_name = row[1].strip() if len(row) > 1 and row[1] else ''
            session_type = SessionType.query.filter_by(Title=session_title_from_csv).first()
            type_id = session_type.id if session_type else None
            session_title = session_type.Title if session_type and session_type.Is_Titleless else session_title_from_csv
            owner_id = None
            if owner_name:
                normalized_name = ' '.join(owner_name.split())
                owner = Contact.query.filter_by(Name=normalized_name).first()
                if owner:
                    owner_id = owner.id
            duration_min, duration_max = None, None
            if len(row) > 3:
                duration_min = row[2].strip() if row[2] else None
                duration_max = row[3].strip() if row[3] else None
            elif len(row) > 2:
                duration_max = row[2].strip() if row[2] else None
            if not duration_max and not duration_min and session_type:
                duration_max = session_type.Duration_Max
                duration_min = session_type.Duration_Min
            new_log = SessionLog(
                Meeting_Number=meeting_number,
                Meeting_Seq=seq,
                Type_ID=type_id,
                Owner_ID=owner_id,
                Session_Title=session_title,
                Duration_Min=duration_min,
                Duration_Max=duration_max
            )
            if session_type and not session_type.Is_Section:
                new_log.Start_Time = current_time
                duration_to_add = int(duration_max) if duration_max else 0
                dt_current_time = datetime.combine(datetime.today(), current_time)
                next_dt = dt_current_time + timedelta(minutes=duration_to_add + 1)
                current_time = next_dt.time()
            db.session.add(new_log)
            seq += 1
        db.session.commit()
        return redirect(url_for('agenda_bp.agenda', meeting_number=meeting_number))
    else:
        return redirect(url_for('agenda_bp.agenda', message='Invalid file type. Please upload a CSV file.', category='error'))

@agenda_bp.route('/agenda/export/<int:meeting_number>')
@login_required
def export_agenda(meeting_number):
    meeting = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
    if not meeting:
        return "Meeting not found", 404

    logs = db.session.query(
        SessionLog.Session_Title,
        Contact.Name,
        SessionLog.Duration_Min,
        SessionLog.Duration_Max,
        SessionType.Title.label('session_type_title'),
        SessionType.Is_Titleless
    ).outerjoin(Contact, SessionLog.Owner_ID == Contact.id)\
     .join(SessionType, SessionLog.Type_ID == SessionType.id, isouter=True)\
     .filter(SessionLog.Meeting_Number == meeting_number)\
     .order_by(SessionLog.Meeting_Seq.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    start_time = meeting.Start_Time.strftime('%H:%M') if meeting.Start_Time else ''
    writer.writerow([meeting.Meeting_Number, start_time])

    for log in logs:
        session_title = log.session_type_title if log.Is_Titleless else log.Session_Title
        writer.writerow([session_title, log.Name or '', log.Duration_Min or '', log.Duration_Max or ''])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'{meeting_number}_agenda.csv'
    )

@agenda_bp.route('/agenda/update', methods=['POST'])
@login_required
def update_logs():
    data = request.get_json()
    if not data:
        return jsonify(success=False, message="No data received"), 400

    try:
        # Since all items are from the same meeting, get the meeting number from the first item.
        meeting_number = data[0].get('meeting_number')
        if not meeting_number:
            return jsonify(success=False, message="Meeting number is missing"), 400

        for seq, item in enumerate(data, 1):
            _create_or_update_session(item, meeting_number, seq)

        # Recalculate start times for the single updated meeting.
        _recalculate_start_times([meeting_number])

        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500

@agenda_bp.route('/agenda/delete/<int:log_id>', methods=['POST'])
@login_required
def delete_log(log_id):
    log = SessionLog.query.get_or_404(log_id)
    try:
        db.session.delete(log)
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500