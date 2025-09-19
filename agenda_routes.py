# vpemaster/agenda_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, send_file
from .main_routes import login_required
from .models import SessionLog, SessionType, Contact, Meeting, Project, SpeechLog
from vpemaster import db
from sqlalchemy import distinct
from datetime import datetime, timedelta
import io
import csv
import re


agenda_bp = Blueprint('agenda_bp', __name__)

def _group_and_sort_sessions(data):
    items_by_meeting = {}
    for item in data:
        meeting_number = item.get('meeting_number')
        if not meeting_number:
            continue
        if meeting_number not in items_by_meeting:
            items_by_meeting[meeting_number] = []
        items_by_meeting[meeting_number].append(item)

    for meeting_number, items in items_by_meeting.items():
        original_logs = SessionLog.query.filter_by(Meeting_Number=meeting_number).all()
        original_seqs = {log.id: log.Meeting_Seq for log in original_logs}

        def sort_key(item):
            new_seq_str = item.get('meeting_seq', '999')
            try:
                new_seq = int(new_seq_str)
            except (ValueError, TypeError):
                new_seq = 999
            item_id_str = item.get('id')
            priority = 0
            if item_id_str == 'new':
                priority = 0
            else:
                try:
                    item_id = int(item_id_str)
                    original_seq = original_seqs.get(item_id)
                    if original_seq == new_seq:
                        priority = 1
                    else:
                        priority = 2
                except (ValueError, TypeError):
                    priority = 0
            return (new_seq, priority)

        items_by_meeting[meeting_number] = sorted(items, key=sort_key)

    return items_by_meeting

def _sync_speech_log_for_session(session_log, meeting):
    """Creates, updates, or deletes a SpeechLog for a session based on its Project_ID."""
    if not session_log:
        return

    existing_speech_log = SpeechLog.query.filter_by(Session_ID=session_log.id).first()

    # Case 1: Session is NOT a project speech. Delete any existing speech log.
    if not session_log.Project_ID:
        if existing_speech_log:
            db.session.delete(existing_speech_log)
        return

    # Case 2: Session IS a project speech. Find contact and project.
    contact = Contact.query.get(session_log.Owner_ID)
    project = Project.query.get(session_log.Project_ID)

    # If contact or project is missing, we can't sync. Delete orphaned log if it exists.
    if not contact or not project:
        if existing_speech_log:
            db.session.delete(existing_speech_log)
        return

    # Determine the correct pathway project code for the Level
    pathway_code = None
    pathway_map = {
        "Dynamic Leadership": project.Code_DL,
        "Engaging Humor": project.Code_EH,
        "Motivational Strategies": project.Code_MS,
        "Persuasive Influence": project.Code_PI,
        "Presentation Mastery": project.Code_PM,
        "Visionary Communication": project.Code_VC
    }
    pathway_code = pathway_map.get(contact.Working_Path)

    # Ensure the meeting object has a date.
    if not meeting.Meeting_Date:
        meeting.Meeting_Date = datetime.today().date()

    # Update existing log or create a new one
    if existing_speech_log:
        existing_speech_log.Meeting_Number = session_log.Meeting_Number
        existing_speech_log.Meeting_Date = meeting.Meeting_Date
        existing_speech_log.Speech_Title = session_log.Session_Title
        existing_speech_log.Pathway = contact.Working_Path
        existing_speech_log.Level = pathway_code
        existing_speech_log.Name = contact.Name
        existing_speech_log.Contact_ID = session_log.Owner_ID
        existing_speech_log.Project_ID = project.ID
        existing_speech_log.Project_Title = project.Project_Name
    else:
        new_speech_log = SpeechLog(
            Meeting_Number=session_log.Meeting_Number,
            Meeting_Date=meeting.Meeting_Date,
            Session='Pathway Speech',
            Speech_Title=session_log.Session_Title,
            Pathway=contact.Working_Path,
            Level=pathway_code,
            Name=contact.Name,
            Contact_ID=session_log.Owner_ID,
            Project_ID=project.ID,
            Project_Title=project.Project_Name,
            Project_Status='Booked',
            Session_ID=session_log.id
        )
        db.session.add(new_speech_log)


def _create_or_update_session(item, meeting_number, seq):
    meeting = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
    if not meeting:
        new_meeting = Meeting(Meeting_Number=meeting_number)
        db.session.add(new_meeting)
        db.session.flush()
        meeting = new_meeting

    if seq == 1 and item.get('start_time'):
        try:
            meeting.Start_Time = datetime.strptime(item.get('start_time'), '%H:%M:%S').time()
        except ValueError:
            meeting.Start_Time = datetime.strptime(item.get('start_time'), '%H:%M').time()

    type_id = item.get('type_id')
    if type_id == '':
        type_id = None

    session_title = item.get('session_title')
    project_id = item.get('project_id') if item.get('project_id') else None

    current_log = None
    if item['id'] == 'new':
        new_log = SessionLog(
            Meeting_Number=meeting_number,
            Meeting_Seq=seq,
            Type_ID=type_id,
            Owner_ID=item['owner_id'] if item['owner_id'] else None,
            Duration_Min=item['duration_min'] if item['duration_min'] else None,
            Duration_Max=item['duration_max'] if item['duration_max'] else None,
            Project_ID=project_id,
            Session_Title=session_title
        )
        db.session.add(new_log)
        db.session.flush()
        current_log = new_log
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

            if session_title is not None:
                log.Session_Title = session_title
            current_log = log

    # Sync speech log after creating/updating the session
    _sync_speech_log_for_session(current_log, meeting)


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

                # Default break is 1 minute
                break_minutes = 1
                # Add an extra minute if the session title starts with "Evaluation"
                if log.Session_Title and log.Session_Title.startswith('Evaluation'):
                    break_minutes += 1

                dt_current_time = datetime.combine(datetime.today(), current_time)
                next_dt = dt_current_time + timedelta(minutes=duration_to_add + break_minutes)
                current_time = next_dt.time()
            else:
                log.Start_Time = None

@agenda_bp.route('/agenda', methods=['GET'])
def agenda():
    """
    Renders the agenda builder page, displaying session logs for a selected meeting.
    """
    # Get all available meeting numbers, latest first
    meeting_numbers_query = db.session.query(distinct(SessionLog.Meeting_Number)).order_by(SessionLog.Meeting_Number.desc()).all()
    meeting_numbers = [num[0] for num in meeting_numbers_query]

    # Get all projects and format them for JavaScript
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

    # Determine the selected meeting from URL, default to the latest one if not provided
    selected_meeting_str = request.args.get('meeting_number')
    if not selected_meeting_str and meeting_numbers:
        selected_meeting = meeting_numbers[0]
    else:
        selected_meeting = selected_meeting_str

    # Base query for logs
    query = db.session.query(
        SessionLog,
        SessionType.Is_Section,
        SessionType.Title.label('session_type_title'),
        SessionType.Is_Titleless,
        Project.Code_DL,
        Project.Code_EH,
        Project.Code_MS,
        Project.Code_PI,
        Project.Code_PM,
        Project.Code_VC,
        SessionLog.Project_ID
    ).join(SessionType, SessionLog.Type_ID == SessionType.id, isouter=True)\
     .outerjoin(Project, SessionLog.Project_ID == Project.ID)


    # Filter by the selected meeting number
    if selected_meeting:
        query = query.filter(SessionLog.Meeting_Number == selected_meeting)

    session_logs = query.order_by(SessionLog.Meeting_Seq.asc()).all()

    # Get data for session types and contacts
    session_types_query = SessionType.query.order_by(SessionType.Title.asc()).all()
    session_types_data = [{"id": s.id, "Title": s.Title, "Is_Section": s.Is_Section, "Valid_for_Project": s.Valid_for_Project} for s in session_types_query]

    contacts_query = Contact.query.order_by(Contact.Name.asc()).all()
    contacts_data = [{"id": c.id, "Name": c.Name, "Working_Path": c.Working_Path,\
                    "Next_Project": c.Next_Project, "DTM": c.DTM, "Type": c.Type,\
                    "Club": c.Club, "Completed_Levels": c.Completed_Levels} for c in contacts_query]

    return render_template('agenda.html',
                           logs=session_logs,
                           session_types=session_types_data,
                           contacts=contacts_data,
                           projects=projects_data,
                           meeting_numbers=meeting_numbers,
                           selected_meeting=int(selected_meeting) if selected_meeting else None)


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
            # Try decoding with UTF-8 first
            decoded_content = file_content.decode('utf-8')
        except UnicodeDecodeError:
            # If UTF-8 fails, try with GBK
            decoded_content = file_content.decode('gbk', errors='replace') # 'replace' will prevent further errors

        stream = io.StringIO(decoded_content, newline=None)

        # 1. Process first line for meeting info
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
            db.session.flush()
        else:
            meeting.Start_Time = current_time # Update start time if meeting exists

        # 2. Process subsequent rows for sessions
        csv_reader = csv.reader(stream)
        seq = 1
        for row in csv_reader:
            if not row: continue # Skip empty rows

            session_title_from_csv = row[0].strip() if len(row) > 0 else ''
            owner_name = row[1].strip() if len(row) > 1 and row[1] else ''

            # 4. Match Session Type
            session_type = SessionType.query.filter_by(Title=session_title_from_csv).first()
            type_id = session_type.id if session_type else None

            session_title = session_type.Title if session_type else session_title_from_csv


            # 6. Match Owner
            owner_id = None
            if owner_name:
                # Normalize whitespace by splitting and rejoining
                normalized_name = ' '.join(owner_name.split())
                owner = Contact.query.filter_by(Name=normalized_name).first()
                if owner:
                    owner_id = owner.id

            # 7. Handle Durations
            duration_min, duration_max = None, None
            if len(row) > 3:
                duration_min = row[2].strip() if row[2] else None
                duration_max = row[3].strip() if row[3] else None
            elif len(row) > 2:
                duration_max = row[2].strip() if row[2] else None

            if not duration_max and not duration_min and session_type:
                duration_max = session_type.Duration_Max
                duration_min = session_type.Duration_Min

            # Create Session Log
            new_log = SessionLog(
                Meeting_Number=meeting_number,
                Meeting_Seq=seq,
                Type_ID=type_id,
                Owner_ID=owner_id,
                Session_Title=session_title,
                Duration_Min=duration_min,
                Duration_Max=duration_max
            )

            # 7. Calculate Start Time for non-sections
            if session_type and not session_type.Is_Section:
                new_log.Start_Time = current_time
                # Calculate next start time
                duration_to_add = int(duration_max) if duration_max else 0
                dt_current_time = datetime.combine(datetime.today(), current_time)
                next_dt = dt_current_time + timedelta(minutes=duration_to_add + 1)
                current_time = next_dt.time()

            db.session.add(new_log)
            seq += 1

        db.session.commit()
        return redirect(url_for('agenda_bp.agenda'))
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
        SessionLog.Duration_Max
    ).outerjoin(Contact, SessionLog.Owner_ID == Contact.id).filter(
        SessionLog.Meeting_Number == meeting_number
    ).order_by(SessionLog.Meeting_Seq.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    # Write the header row
    start_time = meeting.Start_Time.strftime('%H:%M') if meeting.Start_Time else ''
    writer.writerow([meeting.Meeting_Number, start_time])

    # Write the session data
    for log in logs:
        writer.writerow([log.Session_Title, log.Name or '', log.Duration_Min or '', log.Duration_Max or ''])

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
        items_by_meeting = _group_and_sort_sessions(data)

        for meeting_number, items in items_by_meeting.items():
            for seq, item in enumerate(items, 1):
                _create_or_update_session(item, meeting_number, seq)

        _recalculate_start_times(items_by_meeting.keys())

        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@agenda_bp.route('/agenda/delete/<int:log_id>', methods=['POST'])
@login_required
def delete_log(log_id):
    """
    Deletes a session log.
    """
    log = SessionLog.query.get_or_404(log_id)
    try:
        db.session.delete(log)
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


