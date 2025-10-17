# vpemaster/agenda_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, send_file, current_app
from .main_routes import login_required
from .models import SessionLog, SessionType, Contact, Meeting, Project
from vpemaster import db
from sqlalchemy import distinct
from datetime import datetime, timedelta
import io
import csv
import os

agenda_bp = Blueprint('agenda_bp', __name__)

# --- Helper Functions for Data Fetching ---

def _get_agenda_logs(meeting_number):
    """Fetches all agenda logs and related data for a specific meeting."""
    query = db.session.query(
        SessionLog,
        SessionType.Is_Section,
        SessionType.Title.label('session_type_title'),
        SessionType.Predefined,
        SessionType.Is_Hidden,
        Meeting.Meeting_Date,
        Project.Code_DL, Project.Code_EH, Project.Code_MS,
        Project.Code_PI, Project.Code_PM, Project.Code_VC,
        Project.Code_DTM,
        Project.Purpose,
        Project.Project_Name
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

    owner_id_val = item.get('owner_id')
    # Ensure empty strings, the string 'None', or 0 are treated as NULL
    if not owner_id_val or owner_id_val in ['None', '0']:
        owner_id = None
    else:
        owner_id = int(owner_id_val)

    session_title = item.get('session_title')
    designation = item.get('designation')
    project_id = item.get('project_id') if item.get('project_id') else None
    status = item.get('status') if item.get('status') else 'Booked'

    if owner_id and not designation:
        owner = Contact.query.get(owner_id)
        if owner:
            if owner.DTM:
                designation = None
            if owner.Type == 'Guest':
                designation = f"Guest@{owner.Club}" if owner.Club else "Guest"
            elif owner.Type == 'Member':
                designation = owner.Completed_Levels.replace(' ', '/') if owner.Completed_Levels else None

    if designation is None:
        designation = ''


    if item['id'] == 'new':
        new_log = SessionLog(
            Meeting_Number=meeting_number,
            Meeting_Seq=seq,
            Type_ID=type_id,
            Owner_ID=owner_id, # Use corrected variable
            Designation=designation,
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
            log.Owner_ID = owner_id # Use corrected variable
            log.Designation = designation
            log.Duration_Min = item.get('duration_min') if item.get('duration_min') else None
            log.Duration_Max = item.get('duration_max') if item.get('duration_max') else None
            log.Project_ID = project_id
            log.Status = status
            if session_title is not None:
                log.Session_Title = session_title

def _recalculate_start_times(meetings_to_update):
    for meeting in meetings_to_update:
        if not meeting or not meeting.Start_Time or not meeting.Meeting_Date:
            continue

        current_time = meeting.Start_Time
        # Fetch Is_Hidden along with Is_Section
        logs_to_update = db.session.query(SessionLog, SessionType.Is_Section, SessionType.Is_Hidden)\
            .join(SessionType, SessionLog.Type_ID == SessionType.id, isouter=True)\
            .filter(SessionLog.Meeting_Number == meeting.Meeting_Number)\
            .order_by(SessionLog.Meeting_Seq.asc()).all()

        for log, is_section, is_hidden in logs_to_update:
            # --- THIS IS THE FIX ---
            # If the session is a section header OR if it's hidden, set its time to None and continue.
            if is_section or is_hidden:
                log.Start_Time = None
                continue
            # --- END OF FIX ---

            # The rest of the logic only runs for visible, non-section items.
            log.Start_Time = current_time
            duration_to_add = int(log.Duration_Max or 0)
            break_minutes = 1
            # Individual Evaluation Type_ID is 31
            if log.Type_ID == 31 and meeting.GE_Style == 'immediate':
                break_minutes += 1
            dt_current_time = datetime.combine(meeting.Meeting_Date, current_time)
            next_dt = dt_current_time + timedelta(minutes=duration_to_add + break_minutes)
            current_time = next_dt.time()

# --- Main Route ---

@agenda_bp.route('/agenda', methods=['GET'])
def agenda():
    meeting_numbers_query = db.session.query(distinct(SessionLog.Meeting_Number)).order_by(SessionLog.Meeting_Number.desc()).all()
    meeting_numbers = [num[0] for num in meeting_numbers_query]

    selected_meeting_str = request.args.get('meeting_number')
    selected_meeting_num = None

    if selected_meeting_str:
        selected_meeting_num = int(selected_meeting_str)
    else:
        # Find the most recent upcoming meeting number
        upcoming_meeting = Meeting.query\
            .filter(Meeting.Meeting_Date >= datetime.today().date())\
            .order_by(Meeting.Meeting_Date.asc(), Meeting.Meeting_Number.asc())\
            .first()

        if upcoming_meeting:
            selected_meeting_num = upcoming_meeting.Meeting_Number
        elif meeting_numbers:
            # Fallback to the most recent existing meeting (highest meeting number)
            selected_meeting_num = meeting_numbers[0]

    selected_meeting = None
    if selected_meeting_num:
        selected_meeting = Meeting.query.filter_by(Meeting_Number=selected_meeting_num).first()


    session_logs = _get_agenda_logs(selected_meeting_num)
    project_speakers = _get_project_speakers(selected_meeting_num)

    # Data for templates and JavaScript
    projects = Project.query.order_by(Project.Project_Name).all()
    projects_data = [
        {
            "ID": p.ID, "Project_Name": p.Project_Name, "Code_DL": p.Code_DL,
            "Code_EH": p.Code_EH, "Code_MS": p.Code_MS, "Code_PI": p.Code_PI,
            "Code_PM": p.Code_PM, "Code_VC": p.Code_VC, "Code_DTM": p.Code_DTM,
            "Purpose": p.Purpose
        } for p in projects
    ]
    pathways = list(current_app.config['PATHWAY_MAPPING'].keys())
    session_types = SessionType.query.order_by(SessionType.Title.asc()).all()
    session_types_data = [{"id": s.id, "Title": s.Title, "Is_Section": s.Is_Section, "Valid_for_Project": s.Valid_for_Project, "Predefined": s.Predefined} for s in session_types]
    contacts = Contact.query.order_by(Contact.Name.asc()).all()
    contacts_data = [
        {
            "id": c.id, "Name": c.Name, "DTM": c.DTM, "Type": c.Type,
            "Club": c.Club, "Working_Path": c.Working_Path, "Next_Project": c.Next_Project,
            "Completed_Levels": c.Completed_Levels
        } for c in contacts
    ]
    members = Contact.query.filter_by(Type='Member').order_by(Contact.Name.asc()).all()

    template_dir = os.path.join(current_app.static_folder, 'mtg_templates')
    try:
        meeting_templates = [f for f in os.listdir(template_dir) if f.endswith('.csv')]
    except FileNotFoundError:
        meeting_templates = []

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
                           project_speakers=project_speakers,
                           meeting_templates=meeting_templates)


@agenda_bp.route('/agenda/export/<int:meeting_number>')
@login_required
def export_agenda(meeting_number):
    meeting = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
    if not meeting:
        return "Meeting not found", 404

    logs = db.session.query(
        SessionLog,
        SessionType,
        Contact,
        Project
    ).outerjoin(Contact, SessionLog.Owner_ID == Contact.id)\
     .join(SessionType, SessionLog.Type_ID == SessionType.id, isouter=True)\
     .outerjoin(Project, SessionLog.Project_ID == Project.ID)\
     .filter(SessionLog.Meeting_Number == meeting_number)\
     .order_by(SessionLog.Meeting_Seq.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    pathway_mapping = current_app.config['PATHWAY_MAPPING']

    writer.writerow(['Start Time', 'Session Title', 'Owner', 'Duration'])

    for log, session_type, contact, project in logs:
        if session_type and session_type.Is_Section:
            writer.writerow([])
            writer.writerow(['', log.Session_Title or session_type.Title, '', ''])
            continue

        start_time = log.Start_Time.strftime('%H:%M') if log.Start_Time else ''

        # --- FIX for Session and Speech Titles ---
        session_title = log.Session_Title if log.Session_Title else (session_type.Title if session_type else '')

        # 1. Handle "Evaluation for <speaker>" format
        if log.Type_ID == 31 and log.Session_Title: # Individual Evaluation
            session_title = f"Evaluation for {log.Session_Title}"

        # 2. Handle Pathway Speech format
        elif log.Project_ID and contact and contact.Working_Path:
            pathway_abbr = pathway_mapping.get(contact.Working_Path)
            if pathway_abbr and project:
                project_code = getattr(project, f"Code_{pathway_abbr}", None)
                if project_code:
                    title_part = f'"{log.Session_Title}" ' if log.Session_Title else ''
                    session_title = f"{title_part}({pathway_abbr}{project_code})"

        # 3. Clean up double quotes for all titles
        if session_title:
            session_title = session_title.replace('""', '"')

        # --- FIX for Owner Information ---
        owner_info = ''
        if contact:
            owner_info = contact.Name
            meta_parts = []
            if contact.DTM:
                meta_parts.append('DTM')

            if log.Designation:
                 meta_parts.append(log.Designation)
            elif contact.Type == 'Member' and contact.Completed_Levels:
                meta_parts.append(contact.Completed_Levels.replace('/', ' '))

            if meta_parts:
                owner_info += ' - ' + ' '.join(meta_parts)

        duration = ''
        min_dur = log.Duration_Min
        max_dur = log.Duration_Max
        if max_dur is not None:
            if min_dur is not None and min_dur > 0 and min_dur != max_dur:
                duration = f"[{min_dur}'-{max_dur}']"
            else:
                duration = f"[{max_dur}']"

        writer.writerow([
            start_time,
            session_title,
            owner_info,
            duration
        ])

    writer.writerow([])
    writer.writerow(['Speech Projects'])

    speech_projects_query = db.session.query(
        Project,
        Contact.Working_Path,
        SessionLog.Session_Title
    ).join(SessionLog, Project.ID == SessionLog.Project_ID)\
     .join(Contact, SessionLog.Owner_ID == Contact.id)\
     .filter(SessionLog.Meeting_Number == meeting_number)\
     .all()

    projects_to_sort = []
    for project, working_path, speech_title in speech_projects_query:
        pathway_abbr = pathway_mapping.get(working_path)
        if pathway_abbr:
            project_code = getattr(project, f"Code_{pathway_abbr}", None)
            if project_code:
                projects_to_sort.append((project_code, project, working_path, pathway_abbr, speech_title))

    sorted_projects = sorted(projects_to_sort, key=lambda x: x[0])

    elective_codes = ['3.2', '3.3', '4.2', '5.3']

    for project_code, project, working_path, pathway_abbr, speech_title in sorted_projects:
        project_type = "Elective" if project_code in elective_codes else "Required"

        duration = f"[{project.Duration_Min}'-{project.Duration_Max}']"
        title_part = f'"{speech_title}" ' if speech_title else ''

        # Clean up double quotes here as well
        full_title = f"{working_path} ({pathway_abbr}{project_code}) {project.Project_Name} ({project_type}) {duration}"
        writer.writerow([full_title.replace('""', '"')])
        writer.writerow([project.Purpose])
        writer.writerow([])


    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'{meeting_number}_agenda.csv'
    )

@agenda_bp.route('/agenda/create', methods=['POST'])
@login_required
def create_from_template():
    meeting_number = request.form.get('meeting_number')
    meeting_date_str = request.form.get('meeting_date')
    start_time_str = request.form.get('start_time')
    template_file = request.form.get('template_file')
    ge_style = request.form.get('ge_style')

    try:
        meeting_date = datetime.strptime(meeting_date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
    except (ValueError, TypeError):
        return redirect(url_for('agenda_bp.agenda', message='Invalid date or time format.', category='error'))

    meeting = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
    if not meeting:
        meeting = Meeting(Meeting_Number=meeting_number, Meeting_Date=meeting_date, Start_Time=start_time, GE_Style=ge_style)
        db.session.add(meeting)
    else:
        meeting.Meeting_Date = meeting_date
        meeting.Start_Time = start_time
        meeting.GE_Style = ge_style

    SessionLog.query.filter_by(Meeting_Number=meeting_number).delete()
    db.session.commit() # Commit the meeting creation/update

    template_path = os.path.join(current_app.static_folder, 'mtg_templates', template_file)
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            stream = io.StringIO(f.read())
            stream.readline()
            csv_reader = csv.reader(stream)
            seq = 1
            current_time = start_time
            for row in csv_reader:
                if not row or not row[0].strip():
                    continue

                session_title_from_csv = row[0].strip()
                owner_name = row[1].strip() if len(row) > 1 else ''
                duration_min = row[2].strip() if len(row) > 2 else None
                duration_max = row[3].strip() if len(row) > 3 else None

                session_type = SessionType.query.filter_by(Title=session_title_from_csv).first()
                type_id = session_type.id if session_type else None

                if not duration_max and not duration_min and session_type:
                    duration_max = session_type.Duration_Max
                    duration_min = session_type.Duration_Min

                # --- THIS IS THE FIX ---
                # CORRECTED IDs and logic for duration and breaks
                if type_id == 16:  # General Evaluation Report
                    if ge_style == 'immediate':
                        duration_max = 3
                    else:  # deferred
                        duration_max = 5

                break_minutes = 1
                if type_id == 31 and ge_style == 'immediate': # Individual Evaluation
                    break_minutes += 1
                # --- END OF FIX ---

                session_title = session_type.Title if session_type and session_type.Predefined else session_title_from_csv

                # ... (rest of the owner and designation logic is unchanged)
                owner_id = None
                designation = None
                if owner_name:
                    owner = Contact.query.filter_by(Name=owner_name).first()
                    if owner:
                        owner_id = owner.id
                        if owner.DTM:
                            designation = None
                        elif owner.Type == 'Guest':
                            designation = f"Guest@{owner.Club}" if owner.Club else "Guest"
                        elif owner.Type == 'Member':
                            designation = owner.Completed_Levels.replace(' ', '/') if owner.Completed_Levels else None

                if designation is None:
                    designation = ''

                new_log = SessionLog(
                    Meeting_Number=meeting_number,
                    Meeting_Seq=seq,
                    Type_ID=type_id,
                    Owner_ID=owner_id,
                    Session_Title=session_title,
                    Designation=designation,
                    Duration_Min=duration_min,
                    Duration_Max=duration_max
                )

                if session_type and not session_type.Is_Section:
                    new_log.Start_Time = current_time
                    duration_to_add = int(duration_max or 0)
                    dt_current_time = datetime.combine(meeting_date, current_time)
                    # Use the calculated break_minutes
                    next_dt = dt_current_time + timedelta(minutes=duration_to_add + break_minutes)
                    current_time = next_dt.time()

                db.session.add(new_log)
                seq += 1
            db.session.commit()
    except FileNotFoundError:
        return redirect(url_for('agenda_bp.agenda', message=f'Template file not found: {template_file}', category='error'))

    return redirect(url_for('agenda_bp.agenda', meeting_number=meeting_number))



@agenda_bp.route('/agenda/update', methods=['POST'])
@login_required
def update_logs():
    data = request.get_json()
    agenda_data = data.get('agenda_data', [])
    new_style = data.get('ge_style')

    if not agenda_data:
        return jsonify(success=False, message="No data received"), 400

    try:
        meeting_number = agenda_data[0].get('meeting_number')
        if not meeting_number:
            return jsonify(success=False, message="Meeting number is missing"), 400

        meeting = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
        if not meeting:
             return jsonify(success=False, message="Meeting not found"), 404

        # 1. Update and IMMEDIATELY commit the GE style change.
        if new_style and meeting.GE_Style != new_style:
            meeting.GE_Style = new_style
            db.session.commit()

        # 2. Update the duration for the GE Report in the submitted data.
        for item in agenda_data:
            # CORRECTED ID: General Evaluation Report is 16
            if str(item.get('type_id')) == '16':
                if new_style == 'immediate':
                    item['duration_max'] = 3
                else:  # 'deferred'
                    item['duration_max'] = 5
                break

        # 3. Save all session data.
        for seq, item in enumerate(agenda_data, 1):
            _create_or_update_session(item, meeting_number, seq)

        # 4. Recalculate start times using the now-committed GE style.
        _recalculate_start_times([meeting])

        # Commit the final session and time changes.
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