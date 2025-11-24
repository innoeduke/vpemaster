# vpemaster/agenda_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, send_file, current_app
from .auth.utils import login_required
from .models import SessionLog, SessionType, Contact, Meeting, Project, Presentation, Media, Roster, Role
from . import db
from sqlalchemy import distinct, orm
from datetime import datetime, timedelta
import io
import csv
import os
import openpyxl
from openpyxl.styles import Font, Alignment
from io import BytesIO
from .utils import derive_current_path_level, load_setting, derive_designation, project_id_to_code

agenda_bp = Blueprint('agenda_bp', __name__)

# --- Helper Functions for Data Fetching ---

# Table Topics, Prepared Speaker, Pathway Speech, Panel Discussion
speech_types_with_project = {7, 20, 30, 44}


def _get_agenda_logs(meeting_number):
    """Fetches all agenda logs and related data for a specific meeting."""
    query = db.session.query(SessionLog)\
        .options(
            orm.joinedload(SessionLog.session_type).joinedload(SessionType.role),  # Eager load SessionType and Role
            orm.joinedload(SessionLog.meeting),      # Eager load Meeting
            orm.joinedload(SessionLog.project),      # Eager load Project
            orm.joinedload(SessionLog.owner),         # Eager load Owner
            orm.joinedload(SessionLog.media)
    )

    if meeting_number:
        query = query.filter(SessionLog.Meeting_Number == meeting_number)

    # Order by sequence
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
        db.session.flush()  # Flush to get meeting ID if needed, though not strictly required here
        meeting = new_meeting

    type_id = item.get('type_id')
    session_type = SessionType.query.get(
        type_id) if type_id else None  # Get the SessionType object

    # --- Owner ID Handling (no changes needed) ---
    owner_id_val = item.get('owner_id')
    owner_id = int(owner_id_val) if owner_id_val and owner_id_val not in [
        'None', '0'] else None
    owner_contact = Contact.query.get(owner_id) if owner_id else None

    # --- Project ID and Status (no changes needed) ---
    project_id = item.get('project_id')
    if project_id in [None, "", "null"]:
        project_id = None
    status = item.get('status') if item.get('status') else 'Booked'
    session_title = item.get('session_title')

    # --- Designation Logic (no changes needed) ---
    designation = item.get('designation')
    # Check for None or empty string
    if owner_id and (designation is None or designation == ''):
        # Use the centralized utility function
        designation = derive_designation(owner_contact)

    # --- Automatic current_path_level Derivation ---
    temp_log_data = {
        'Project_ID': project_id,
        'Type_ID': type_id,
        'session_type': session_type,  # Pass fetched session_type
        # Fetch project if needed
        'project': Project.query.get(project_id) if project_id else None
    }
    # Create a temporary object-like structure or fetch existing log if updating
    log_for_derivation = SessionLog.query.get(item['id']) if item.get(
        'id') != 'new' else type('obj', (object,), temp_log_data)()
    if item.get('id') == 'new':  # If new, update the temp obj with necessary fields
        log_for_derivation.Project_ID = project_id
        log_for_derivation.Type_ID = type_id
        log_for_derivation.session_type = session_type
        log_for_derivation.project = temp_log_data['project']

    current_path_level = derive_current_path_level(
        log_for_derivation, owner_contact)

    # --- Create or Update SessionLog ---
    if item['id'] == 'new':
        new_log = SessionLog(
            Meeting_Number=meeting_number,
            Meeting_Seq=seq,
            Type_ID=type_id,
            Owner_ID=owner_id,
            Designation=designation,
            Duration_Min=item.get('duration_min') if item.get(
                'duration_min') else None,
            Duration_Max=item.get('duration_max') if item.get(
                'duration_max') else None,
            Project_ID=project_id,
            Session_Title=session_title,
            Status=status,
            current_path_level=current_path_level
        )
        db.session.add(new_log)
    else:
        log = SessionLog.query.get(item['id'])
        if log:
            log.Meeting_Number = meeting_number
            log.Meeting_Seq = seq
            log.Type_ID = type_id
            log.Owner_ID = owner_id
            log.Designation = designation
            log.Duration_Min = item.get('duration_min') if item.get(
                'duration_min') else None
            log.Duration_Max = item.get('duration_max') if item.get(
                'duration_max') else None
            log.Project_ID = project_id
            log.Status = status
            if session_title is not None:
                log.Session_Title = session_title
            log.current_path_level = current_path_level


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
            # If the session is a section header OR if it's hidden, set its time to None and continue.
            if is_section or is_hidden:
                log.Start_Time = None
                continue

            # The rest of the logic only runs for visible, non-section items.
            log.Start_Time = current_time
            duration_to_add = int(log.Duration_Max or 0)
            break_minutes = 1
            # For "Multiple shots" style, add an extra minute break after each evaluation
            if log.Type_ID == 31 and meeting.GE_Style == 'Multiple shots':
                break_minutes += 1
            dt_current_time = datetime.combine(
                meeting.Meeting_Date, current_time)
            next_dt = dt_current_time + \
                timedelta(minutes=duration_to_add + break_minutes)
            current_time = next_dt.time()

# --- Main Route ---


@agenda_bp.route('/agenda', methods=['GET'])
def agenda():

    # --- Determine Selected Meeting ---
    today = datetime.today().date()

    # Subquery to get meeting numbers that have at least one session log
    subquery = db.session.query(distinct(SessionLog.Meeting_Number)).subquery()

    # Query for future meetings that have an agenda
    future_meetings_q = Meeting.query.filter(
        Meeting.Meeting_Number.in_(subquery),
        Meeting.Meeting_Date >= today
    )

    # Query for the 8 most recent past meetings that have an agenda
    past_meetings_q = Meeting.query.filter(
        Meeting.Meeting_Number.in_(subquery),
        Meeting.Meeting_Date < today
    ).order_by(Meeting.Meeting_Date.desc()).limit(8)

    # Execute queries
    future_meetings = future_meetings_q.all()
    past_meetings = past_meetings_q.all()

    # Combine, sort, and get meeting numbers
    all_meetings = sorted(
        future_meetings + past_meetings, key=lambda m: m.Meeting_Date, reverse=True)
    meeting_numbers = [m.Meeting_Number for m in all_meetings]

    selected_meeting_str = request.args.get('meeting_number')
    selected_meeting_num = None

    if selected_meeting_str:
        try:
            selected_meeting_num = int(selected_meeting_str)
        except ValueError:
            # Handle invalid meeting number string if necessary
            selected_meeting_num = None  # Or redirect, flash error
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
        selected_meeting = Meeting.query.options(
            orm.joinedload(Meeting.best_tt_speaker),
            orm.joinedload(Meeting.best_evaluator),
            orm.joinedload(Meeting.best_speaker),
            orm.joinedload(Meeting.best_roletaker),
            orm.joinedload(Meeting.media)
        ).filter(Meeting.Meeting_Number == selected_meeting_num).first()

    # Create a lookup map for award winners. Key: Contact ID, Value: list of award categories.
    award_winner_map = {}
    if selected_meeting:
        def add_winner(contact_id, award_category):
            if not contact_id:
                return
            if contact_id not in award_winner_map:
                award_winner_map[contact_id] = []
            award_winner_map[contact_id].append(award_category)
        add_winner(selected_meeting.Best_Speaker_ID,
                   current_app.config['BEST_SPEAKER'])
        add_winner(selected_meeting.Best_Evaluator_ID,
                   current_app.config['BEST_EVALUATOR'])
        add_winner(selected_meeting.Best_TT_ID, current_app.config['BEST_TT'])
        add_winner(selected_meeting.Best_Roletaker_ID,
                   current_app.config['BEST_ROLETAKER'])

    # --- Fetch Raw Data ---
    raw_session_logs = _get_agenda_logs(selected_meeting_num)
    project_speakers = _get_project_speakers(selected_meeting_num)

    # Pre-fetch award category roles from config for efficiency
    award_categories_roles = current_app.config.get(
        'AWARD_CATEGORIES_ROLES', {})

    all_presentations = Presentation.query.order_by(
        Presentation.level, Presentation.code).all()
    presentation_series = sorted(
        list(set(p.series for p in all_presentations if p.series)))
    presentations_data = [
        {"id": p.id, "title": p.title, "level": p.level,
            "series": p.series, "code": p.code}
        for p in all_presentations
    ]

    # --- Process Raw Logs into Dictionaries ---
    logs_data = []
    pathway_mapping = current_app.config['PATHWAY_MAPPING']
    for log in raw_session_logs:
        session_type = log.session_type
        meeting = log.meeting
        project = log.project
        owner = log.owner
        media = log.media

        # Determine project code if applicable
        project_code_str = None
        session_title_for_dict = log.Session_Title
        project_name_for_dict = project.Project_Name if project else ''
        project_purpose_for_dict = project.Purpose if project else ''
        pathway_code_for_dict = None
        level_for_dict = None

        if session_type and session_type.Title == 'Presentation' and log.Project_ID:
            # Find in the already-fetched list
            presentation = next(
                (p for p in all_presentations if p.id == log.Project_ID), None)
            if presentation:
                if not session_title_for_dict:
                    session_title_for_dict = presentation.title
                project_name_for_dict = presentation.series  # For tooltip
                project_purpose_for_dict = f"Level {presentation.level} - {presentation.title}"

                series_key = " ".join(
                    presentation.series.split()) if presentation.series else ""

                series_initial = current_app.config['SERIES_INITIALS'].get(
                    series_key, "")
                project_code_str = f"{series_initial}{presentation.code}"
        elif log.Project_ID == 60:
            project_code_str = "TM1.0"
        elif project and owner and owner.user and owner.user.Current_Path:  # Else if pathway...
            pathway_suffix = pathway_mapping.get(owner.user.Current_Path)
            if pathway_suffix:
                project_code_val = getattr(
                    project, f"Code_{pathway_suffix}", None)
                if project_code_val:
                    project_code_str = f"{pathway_suffix}{project_code_val}"
                    pathway_code_for_dict = pathway_suffix
                    try:
                        level_for_dict = int(project_code_val.split('.')[0])
                    except (ValueError, IndexError):
                        level_for_dict = None

        # --- Award Logic ---
        award_type = None
        # Check if the log's owner is a winner
        if log.Owner_ID and log.Owner_ID in award_winner_map and log.session_type and log.session_type.role:
            # A person can win multiple awards, so we check each one.
            awards_won = award_winner_map[log.Owner_ID]
            for award_category in awards_won:
                # Check if the role of the current log is eligible for this specific award
                if log.session_type.role.name in award_categories_roles.get(award_category, []):
                    # Format for display (e.g., "Best Speaker")
                    award_type = award_category.replace('_', ' ')
                    break  # Found the matching award for this role, no need to check further

        speaker_is_dtm = False
        if session_type and session_type.Title == 'Evaluation' and log.Session_Title:
            speaker = Contact.query.filter_by(Name=log.Session_Title).first()
            if speaker and speaker.DTM:
                speaker_is_dtm = True

        log_dict = {
            # SessionLog fields
            'id': log.id,
            'Project_ID': log.Project_ID,
            'Meeting_Number': log.Meeting_Number,
            'Meeting_Seq': log.Meeting_Seq,
            'Start_Time_str': log.Start_Time.strftime('%H:%M') if log.Start_Time else '',
            'Session_Title': session_title_for_dict,
            'Type_ID': log.Type_ID,
            'Owner_ID': log.Owner_ID,
            'Designation': log.Designation,
            'Duration_Min': log.Duration_Min,
            'Duration_Max': log.Duration_Max,
            'Status': log.Status,
            'current_path_level': log.current_path_level,
            # SessionType fields
            'is_section': session_type.Is_Section if session_type else False,
            'session_type_title': session_type.Title if session_type else 'Unknown Type',
            'predefined': session_type.Predefined if session_type else False,
            'is_hidden': session_type.Is_Hidden if session_type else False,
            'role': session_type.role.name if session_type and session_type.role else '',
            'valid_for_project': session_type.Valid_for_Project if session_type else False,
            # Meeting fields
            'meeting_date_str': meeting.Meeting_Date.strftime('%Y-%m-%d') if meeting and meeting.Meeting_Date else '',
            'meeting_date_formatted': meeting.Meeting_Date.strftime('%B %d, %Y') if meeting and meeting.Meeting_Date else '',
            # Project fields
            'project_name': project_name_for_dict,
            'project_purpose': project_purpose_for_dict,
            'project_code_display': project_code_str,
            'pathway_code': pathway_code_for_dict,
            'level': level_for_dict,
            # Owner fields
            'owner_name': owner.Name if owner else '',
            'owner_dtm': owner.DTM if owner else False,
            'owner_type': owner.Type if owner else '',
            'owner_club': owner.Club if owner else '',
            'owner_completed_levels': owner.Completed_Paths if owner else '',
            'media_url': media.url if media and media.url else None,
            # Add award type if this specific role won the award
            'award_type': award_type,
            'speaker_is_dtm': speaker_is_dtm
        }
        logs_data.append(log_dict)

    template_dir = os.path.join(current_app.static_folder, 'mtg_templates')
    try:
        meeting_templates = [f for f in os.listdir(
            template_dir) if f.endswith('.csv')]
    except FileNotFoundError:
        meeting_templates = []

    # --- Minimal Data for Initial Page Load ---
    pathways = list(current_app.config['PATHWAY_MAPPING'].keys())
    members = Contact.query.filter_by(
        Type='Member').order_by(Contact.Name.asc()).all()

    default_start_time = load_setting(
        'ClubSettings', 'Meeting Start Time', default='18:55')

    # --- Render Template ---
    return render_template('agenda.html',
                           logs_data=logs_data,               # Use the processed list of dictionaries
                           pathways=pathways,               # For modals
                           pathway_mapping=current_app.config['PATHWAY_MAPPING'],
                           meeting_numbers=meeting_numbers,
                           selected_meeting=selected_meeting,  # Pass the Meeting object
                           members=members,                 # If needed elsewhere
                           project_speakers=project_speakers,  # For JS
                           meeting_templates=meeting_templates,
                           meeting_types=current_app.config['MEETING_TYPES'],
                           default_start_time=default_start_time)


# --- API Endpoints for Asynchronous Data Loading ---

@agenda_bp.route('/api/data/all')
@login_required
def get_all_data_for_modals():
    """
A single endpoint to fetch all data needed for the agenda modals.
    This is called once by the frontend after the initial page load.
    """
    # Session Types
    session_types = SessionType.query.options(orm.joinedload(SessionType.role)).order_by(SessionType.Title.asc()).all()
    session_types_data = [
        {
            "id": s.id, "Title": s.Title, "Is_Section": s.Is_Section,
            "Valid_for_Project": s.Valid_for_Project, "Predefined": s.Predefined,
            "Role": s.role.name if s.role else '', "Role_Group": s.role.type if s.role else '',
            "Duration_Min": s.Duration_Min, "Duration_Max": s.Duration_Max
        } for s in session_types
    ]

    # Contacts
    contacts = Contact.query.options(orm.joinedload(
        Contact.user)).order_by(Contact.Name.asc()).all()
    contacts_data = [
        {
            "id": c.id, "Name": c.Name, "DTM": c.DTM, "Type": c.Type,
            "Club": c.Club, "Completed_Paths": c.Completed_Paths,
            "Current_Path": c.user.Current_Path if c.user else None,
            "Next_Project": c.user.Next_Project if c.user else None
        } for c in contacts
    ]

    # Projects
    projects = Project.query.order_by(Project.Project_Name).all()
    projects_data = [
        {
            "ID": p.ID, "Project_Name": p.Project_Name, "Code_DL": p.Code_DL,
            "Code_EH": p.Code_EH, "Code_MS": p.Code_MS, "Code_PI": p.Code_PI,
            "Code_PM": p.Code_PM, "Code_VC": p.Code_VC, "Code_DTM": p.Code_DTM,
            "Purpose": p.Purpose, "Duration_Min": p.Duration_Min, "Duration_Max": p.Duration_Max
        } for p in projects
    ]

    # Presentations
    all_presentations = Presentation.query.order_by(
        Presentation.level, Presentation.code).all()
    presentations_data = [
        {"id": p.id, "title": p.title, "level": p.level,
            "series": p.series, "code": p.code}
        for p in all_presentations
    ]
    presentation_series = sorted(
        list(set(p.series for p in all_presentations if p.series)))

    return jsonify({
        'session_types': session_types_data,
        'contacts': contacts_data,
        'projects': projects_data,
        'presentations': presentations_data,
        'presentation_series': presentation_series,
        'series_initials': current_app.config['SERIES_INITIALS'],
        'meeting_types': current_app.config['MEETING_TYPES'],
        'meeting_roles': current_app.config['ROLES']
    })


def _get_export_data(meeting_number):
    """
    Fetches the main agenda log data for the export,
    eagerly loading all required related objects.
    """
    return db.session.query(
        SessionLog,
        SessionType,
        Contact,
        Project,
        Media
    ).outerjoin(Contact, SessionLog.Owner_ID == Contact.id)\
     .join(SessionType, SessionLog.Type_ID == SessionType.id, isouter=True)\
     .outerjoin(Project, SessionLog.Project_ID == Project.ID)\
     .outerjoin(Media, SessionLog.id == Media.log_id)\
     .filter(SessionLog.Meeting_Number == meeting_number)\
     .order_by(SessionLog.Meeting_Seq.asc()).all()


def _get_project_type(project_code):
    """Determines if a project is 'Required' or 'Elective' based on its level code."""
    if not project_code:
        return "Elective"  # Default if no code is provided

    # Handle presentation projects (e.g., 'SC101', 'BS203') which are always elective.
    if project_code.startswith(("SC", "BS", "LE")):
        return "Elective"

    # Define a set of all required project codes for higher levels for quick lookup
    required_project_codes = {"3.1", "4.1", "5.1", "5.3"}

    if project_code in required_project_codes:
        return "Required"

    try:
        # Assumes code is in "L.P" format, e.g., "1.1", "3.2"
        level = int(project_code.split('.')[0])
        # Projects in Levels 1 and 2 are also required.
        if level <= 2:
            return "Required"
    except (ValueError, IndexError):
        # If the code is malformed, it won't match the level check,
        # and it wouldn't have matched the specific codes either.
        pass

    # If none of the above conditions are met, it's an elective project.
    return "Elective"


def _get_all_speech_details(logs_data, pathway_mapping):
    """
    Processes logs_data to extract a structured list of speech details.
    """
    speeches = []
    # Define speech session types that require similar handling

    for log, session_type, contact, project, media in logs_data:
        if not log.Project_ID or not session_type:
            continue

        # Handle Pathway Speech types (Type IDs 7, 20, 30, 44) which all use the same logic
        if session_type.id in speech_types_with_project and project:
            user = contact.user if contact else None
            path_abbr = pathway_mapping.get(
                user.Current_Path, "") if user else ""
            project_code = project_id_to_code(
                log.Project_ID, path_abbr) if path_abbr else None
            purpose = project.Purpose
            # For pathway speeches, the project code is just the level.number (e.g., "1.1")
            pathway_project_code = getattr(
                project, f"Code_{path_abbr}", None) if path_abbr else None
            project_type = _get_project_type(pathway_project_code)

            project_name = project.Project_Name
            pathway_name = user.Current_Path if user else ""
            title = log.Session_Title or project.Project_Name
            duration = f"[{project.Duration_Min}'-{project.Duration_Max}']"

            details_to_add = {
                "speech_title": title, "project_name": project_name, "pathway_name": pathway_name, "project_purpose": purpose,
                "project_code": project_code, "duration": duration, "project_type": project_type
            }
            speeches.append(details_to_add)

        # Handle Presentation (Type ID 43) which has special handling
        elif session_type.id == 43:
            presentation = Presentation.query.get(log.Project_ID)
            SERIES_INITIALS = current_app.config['SERIES_INITIALS']
            if not presentation:
                continue
            series_initial = SERIES_INITIALS.get(presentation.series, "")
            presentation_code = project_id_to_code(
                log.Project_ID, series_initial)
            details_to_add = {
                "speech_title": log.Session_Title or presentation.title,
                "project_name": presentation.title,
                "pathway_name": presentation.series,
                "project_purpose": f"Level {presentation.level} - {presentation.title}",
                "project_code": presentation_code,
                "duration": "[10'-15']", "project_type": _get_project_type(presentation_code)
            }
            speeches.append(details_to_add)

    return speeches


def _format_export_row(log, session_type, contact, project, pathway_mapping):
    """Formats a single row for the human-readable agenda (Sheet 1)."""
    if session_type and session_type.Is_Section:
        return ('section', ['', log.Session_Title or session_type.Title, '', ''])

    start_time = log.Start_Time.strftime('%H:%M') if log.Start_Time else ''

    SERIES_INITIALS = current_app.config['SERIES_INITIALS']
    session_title_str = log.Session_Title or (
        session_type.Title if session_type else '')
    project_code_str = None

    if log.Project_ID == 60:
        project_code_str = "TM1.0"
        if not log.Session_Title and project:
            session_title_str = project.Project_Name

    # Check for Pathway Speech (Type 30)
    if session_type and session_type.id == 30 and project:
        # Use the helper function to get project code
        if contact and contact.user and contact.user.Current_Path and log.Project_ID:
            pathway_abbr = pathway_mapping.get(contact.user.Current_Path)
            if pathway_abbr:
                project_code_str = project_id_to_code(
                    log.Project_ID, pathway_abbr)
        if not log.Session_Title:  # If title is blank, use project name
            session_title_str = project.Project_Name

    # Check for Presentation (Type 43)
    elif session_type and session_type.id == 43 and log.Project_ID:
        # We must query Presentation table here, as 'project' will be None
        presentation = Presentation.query.get(log.Project_ID)
        if presentation:
            series_key = " ".join(
                presentation.series.split()) if presentation.series else ""
            series_initial = SERIES_INITIALS.get(series_key, "")
            project_code_str = f"{series_initial}{presentation.code}"
            if not log.Session_Title:  # If title is blank, use presentation title
                session_title_str = presentation.title

    # Check for Individual Evaluator (Type 31)
    if session_type and session_type.id == 31 and log.Session_Title:
        speaker_name = log.Session_Title
        speaker = Contact.query.filter_by(Name=speaker_name).first()
        if speaker and speaker.DTM:
            speaker_name += '\u1D30\u1D40\u1D39'
        session_title_str = f"Evaluation for {speaker_name}"

    # Format the final title
    if project_code_str:
        # Add quotes, removing any existing ones first
        title_part = f'"{session_title_str.replace("`", "").replace("`", "")}"'
        session_title = f"{project_code_str} {title_part}"
    else:
        session_title = session_title_str

    if session_title:
        session_title = session_title.replace('""', '"')

    # Owner Information
    owner_info = ''
    if contact:
        owner_info = contact.Name
        if contact.DTM:
            owner_info += '\u1D30\u1D40\u1D39'  # Unicode for superscript D, T, M

        meta_parts = []
        if log.Designation and not contact.DTM:
            meta_parts.append(log.Designation)
        elif contact.Type == 'Member' and contact.Completed_Paths and not contact.DTM:
            meta_parts.append(contact.Completed_Paths.replace('/', ' '))

        if meta_parts:
            owner_info += ' - ' + ' '.join(meta_parts)

    # Duration
    duration = ''
    min_dur = log.Duration_Min
    max_dur = log.Duration_Max
    if max_dur is not None:
        if min_dur is not None and min_dur > 0 and min_dur != max_dur:
            duration = f"[{min_dur}'-{max_dur}']"
        else:
            duration = f"[{max_dur}']"

    return ('row', [start_time, session_title, owner_info, duration])


def _auto_fit_worksheet_columns(ws, min_width=5):
    """Auto-fits the columns of a given openpyxl worksheet."""
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        adjusted_width = (max_length + 2)

        if adjusted_width > 50:
            adjusted_width = 50

        if adjusted_width < min_width:
            adjusted_width = min_width
        ws.column_dimensions[column].width = adjusted_width


def _build_sheet1(ws, logs_data, speech_details_list, pathway_mapping):
    """Populates Sheet 1 (Agenda) of the workbook."""
    ws.title = "Agenda"
    ws.append(['Start Time', 'Session Title', 'Owner', 'Duration'])
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for log, session_type, contact, project, media in logs_data:
        # Filter: Only include items with a Start Time OR Section Headers
        if log.Start_Time is not None or (session_type and session_type.Is_Section):
            row_type, data = _format_export_row(
                log, session_type, contact, project, pathway_mapping)
            if row_type == 'section':
                ws.append([])  # Blank row
                ws.append(data)
            else:
                ws.append(data)

    ws.append([])
    ws.append(['', 'Speech Projects'])  # Add empty A cell for alignment
    ws['B' + str(ws.max_row)].font = Font(bold=True)

    # Manually add speech projects from the speech_details_list
    for speech in speech_details_list:
        project_type_str = f'({speech["project_type"]}) ' if speech.get(
            "project_type") else ''
        title = f'{speech["pathway_name"]} ({speech["project_code"]}) {speech["project_name"]} {project_type_str}{speech["duration"]}'
        ws.append([None, title])
        if speech.get("project_purpose"):
            purpose_text = speech["project_purpose"]
            ws.append([None, purpose_text])

        ws.append([])

    _auto_fit_worksheet_columns(ws, min_width=5)


def _build_sheet3_roster(ws, meeting_number):
    """Populates Sheet 3 (Roster) of the workbook."""
    ws.title = "Roster"
    ws.append(['Order', 'Name', 'Ticket Class'])
    for cell in ws[1]:
        cell.font = Font(bold=True)

    roster_entries = Roster.query.options(orm.joinedload(Roster.contact)).filter_by(
        meeting_number=meeting_number).order_by(Roster.order_number).all()

    for entry in roster_entries:
        ws.append([
            entry.order_number,
            entry.contact.Name if entry.contact else '',
            entry.ticket
        ])

    _auto_fit_worksheet_columns(ws, min_width=10)


def _build_sheet2_powerbi(ws, meeting, logs_data, speech_details_list, pathway_mapping):
    """Populates Sheet 2 in the PowerBI data dump format."""
    ws.title = "PowerBI Data"

    wrap_alignment = Alignment(wrap_text=True, vertical='top')

    # Helper to find specific logs
    def find_log(type_id):
        for log, st, contact, proj, med in logs_data:
            if st.id == type_id:
                return log, st, contact, proj, med
        return None, None, None, None, None

    # --- 1. MEETING MASTER ---
    ws.append(["1. MEETING MASTER"])
    ws.append([])
    ws.append([
        "Excomm", "Meeting Date", "Meeting Number", "Meeting Title",
        "Keynote Speaker", "Meeting Video Url", "Word of the Day",
        "Best Topic Speaker", "Best Role Taker", "Best Speaker", "Best Evaluator"
    ])

    # Get data for this section
    meeting_types_dict = current_app.config.get('MEETING_TYPES', {})
    master_log, master_st, master_contact = None, None, None  # Default to None

    if meeting.type and meeting.type in meeting_types_dict:
        target_session_type_id = meeting_types_dict[meeting.type].get(
            'owner_role_id')
        if target_session_type_id:
            # Find the log matching the SessionType ID from the config dict
            master_log, master_st, master_contact, _, _ = find_log(
                target_session_type_id)
    gram_log, gram_st, _, _, _ = find_log(7)  # 7 = Grammarian Intro
    term = load_setting('ClubSettings', 'Term', default='')
    excomm_name = load_setting('ClubSettings', 'Excomm Name', default='')
    excomm_string = f'{term} "{excomm_name}"'.strip()

    master_data = [
        excomm_string,
        meeting.Meeting_Date.strftime('%Y/%m/%d'),
        meeting.Meeting_Number,
        meeting.Meeting_Title,
        master_contact.Name if master_contact else "",  # Sharing Master
        meeting.media.url if meeting.media else "",  # Meeting Video Url
        meeting.WOD if meeting.WOD else "",
        meeting.best_tt_speaker.Name if meeting.best_tt_speaker else "",
        meeting.best_roletaker.Name if meeting.best_roletaker else "",
        meeting.best_speaker.Name if meeting.best_speaker else "",
        meeting.best_evaluator.Name if meeting.best_evaluator else ""
    ]
    ws.append(master_data)
    for cell in ws[ws.max_row]:
        if cell.value and isinstance(cell.value, str) and len(cell.value) > 50:
            cell.alignment = wrap_alignment

    ws.append([])
    ws.append([])

    # --- 2. MEETING AGENDA ---
    ws.append(["2. MEETING AGENDA"])
    ws.append([])
    ws.append(["Meeting Number", "Start Time", "Title", "Duration", "Owner"])

    for log, st, contact, proj, med in logs_data:
        if st.Is_Section or st.Is_Hidden:
            continue  # Skip section headers for this part

        # Get formatted title
        _, data = _format_export_row(log, st, contact, proj, pathway_mapping)
        title = data[1]  # Get the formatted title

        # Get duration
        duration = ''
        if log.Duration_Max is not None:
            if log.Duration_Min is not None and log.Duration_Min > 0 and log.Duration_Min != log.Duration_Max:
                duration = f"[{log.Duration_Min}'-{log.Duration_Max}']"
            else:
                duration = f"[{log.Duration_Max}']"

        owner_name = ""
        if contact:
            owner_name = contact.Name
            if contact.Type == 'Guest':
                owner_name += " (Guest)"

        row_data = [
            log.Meeting_Number,
            log.Start_Time.strftime('%H:%M') if log.Start_Time else "",
            title,
            duration,
            owner_name
        ]

        ws.append(row_data)
        for cell in ws[ws.max_row]:
            if cell.value and isinstance(cell.value, str) and len(cell.value) > 50:
                cell.alignment = wrap_alignment

    ws.append([])
    ws.append([])

    # --- 3. YOODLI LINKS (NEW SECTION) ---
    ws.append(["3. YOODLI LINKS"])
    ws.append([])
    # Add 3 blank columns (None) after "Speaker"
    ws.append([
        "Meeting Number", "Speaker",
        None, None, None,  # <-- ADDED 3 BLANK COLUMNS
        "Speaker Yoodli", "Evaluator", "Evaluator Yoodli"
    ])

    # Separate speakers and evaluators from the main data list
    # Include sessions of specific types that are not evaluations (id != 31)
    # Table Topics, Prepared Speaker, Pathway Speech, Panel Discussion
    # But only include Table Topics if it's a valid project (has Valid_for_Project flag)
    SPEAKER_TYPE_IDS = speech_types_with_project | {43}  # 43 = Presentation
    speakers = [(log, st, contact, proj, med) for log, st, contact, proj, med in logs_data
                # Special handling for Table Topics
                if (st.id in SPEAKER_TYPE_IDS and log.Project_ID)]
    # Type 31 = Individual Evaluator
    evaluators = [(log, st, contact, proj, med) for log, st, contact, proj, med in logs_data
                  if st.id == 31]

    # Create a lookup map for evaluators
    # Key: The name of the speaker being evaluated (from evaluator's Session_Title),
    # Value: (Evaluator Name with Guest tag, Evaluator Media URL)
    evaluator_map = {}
    for log, st, contact, proj, med in evaluators:
        speaker_being_evaluated = log.Session_Title
        if speaker_being_evaluated:  # Only add if the evaluator is linked to a speaker
            evaluator_name = contact.Name if contact else ''
            # Add (Guest) tag directly when building the map
            if contact and contact.Type == 'Guest':
                evaluator_name = f"{evaluator_name} (Guest)"
            evaluator_map[speaker_being_evaluated] = (
                evaluator_name, med.url if med else '')

    # Iterate through speakers and find their matching evaluator
    for log, st, contact, proj, med in speakers:
        speaker_name = contact.Name if contact else ''
        speaker_media_url = med.url if med else ''

        # Get project code if available - using the helper function
        project_code_str = ""
        if contact and contact.user and contact.user.Current_Path and log.Project_ID:
            pathway_abbr = pathway_mapping.get(contact.user.Current_Path)
            if pathway_abbr:
                # Use the helper function to get project code with path prefix
                project_code_str = project_id_to_code(
                    log.Project_ID, pathway_abbr)

        # Find the evaluator data from the map using the speaker's name as the key
        # The evaluator name returned already includes the (Guest) tag if applicable
        evaluator_name, evaluator_media_url = evaluator_map.get(
            speaker_name, ('', ''))

        # Add project code to speaker name for display if available
        display_speaker_name = speaker_name
        if project_code_str:
            display_speaker_name = f"{speaker_name} {project_code_str}"

        # Add 3 blank columns (None) after speaker_name
        row_data = [
            meeting.Meeting_Number,
            display_speaker_name,
            None, None, None,  # <-- ADDED 3 BLANK COLUMNS
            speaker_media_url,
            evaluator_name,
            evaluator_media_url
        ]

        ws.append(row_data)
        for cell in ws[ws.max_row]:
            if cell.value and isinstance(cell.value, str) and len(cell.value) > 50:
                cell.alignment = wrap_alignment

    _auto_fit_worksheet_columns(ws, min_width=10)


@agenda_bp.route('/agenda/export/<int:meeting_number>')
@login_required
def export_agenda(meeting_number):
    """
    Generates a three-sheet XLSX export of the agenda.
    Sheet 1: Timed, formatted agenda.
    Sheet 2: PowerBI-style raw data dump.
    Sheet 3: Roster for the meeting.
    """
    meeting = Meeting.query.options(
        orm.joinedload(Meeting.best_tt_speaker),
        orm.joinedload(Meeting.best_evaluator),
        orm.joinedload(Meeting.best_speaker),
        orm.joinedload(Meeting.best_roletaker),
        orm.joinedload(Meeting.media)
    ).filter_by(Meeting_Number=meeting_number).first()
    if not meeting:
        return "Meeting not found", 404

    # 1. Fetch and Prepare Data
    pathway_mapping = current_app.config['PATHWAY_MAPPING']
    logs_data = _get_export_data(meeting_number)
    speech_details_list = _get_all_speech_details(logs_data, pathway_mapping)

    # 2. Create Workbook and Sheets
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws2 = wb.create_sheet(title="PowerBI Data")
    ws3 = wb.create_sheet(title="Roster")

    # 3. Build Sheets
    _build_sheet1(ws1, logs_data, speech_details_list, pathway_mapping)
    _build_sheet2_powerbi(ws2, meeting, logs_data,
                          speech_details_list, pathway_mapping)
    _build_sheet3_roster(ws3, meeting_number)

    # 4. Save and Send
    output_stream = io.BytesIO()
    wb.save(output_stream)
    output_stream.seek(0)

    return send_file(
        output_stream,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'{meeting_number}_agenda_full.xlsx'
    )


@agenda_bp.route('/agenda/create', methods=['POST'])
@login_required
def create_from_template():
    # --- 1. Get ALL form data ---
    meeting_number = request.form.get('meeting_number')
    meeting_date_str = request.form.get('meeting_date')
    start_time_str = request.form.get('start_time')
    meeting_type = request.form.get('meeting_type')
    ge_style = request.form.get('ge_style')

    # --- Get NEW form data ---

    # Look up the template file from the meeting type
    meeting_types_dict = current_app.config.get('MEETING_TYPES', {})
    template_file = meeting_types_dict.get(meeting_type, {}).get('template')
    if not template_file:
        return redirect(url_for('agenda_bp.agenda', message=f'Invalid meeting type: {meeting_type}', category='error'))

    meeting_title = request.form.get('meeting_title')
    subtitle = request.form.get('subtitle')
    wod = request.form.get('wod')
    media_url = request.form.get('media_url')

    try:
        meeting_date = datetime.strptime(meeting_date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
    except (ValueError, TypeError):
        return redirect(url_for('agenda_bp.agenda', message='Invalid date or time format.', category='error'))

    # --- 2. Handle Media URL ---
    # We must create a Media object to get its ID, per your models.py
    new_media_id = None
    if media_url:
        # Check if a Media object with this URL already exists
        existing_media = Media.query.filter_by(url=media_url).first()
        if existing_media:
            new_media_id = existing_media.id
        else:
            # Create a new Media object
            new_media = Media(url=media_url)
            db.session.add(new_media)
            # Flush the session to get the new_media.id before we commit
            db.session.flush()
            new_media_id = new_media.id

    # --- 3. Create or Update Meeting ---
    meeting = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
    if not meeting:
        meeting = Meeting(
            Meeting_Number=meeting_number,
            Meeting_Date=meeting_date,
            Start_Time=start_time,
            GE_Style=ge_style,
            type=meeting_type,
            Meeting_Title=meeting_title,
            Subtitle=subtitle,
            WOD=wod,
            media_id=new_media_id,
            status='not started'  # 添加status字段的默认值
        )
        db.session.add(meeting)
    else:
        meeting.Meeting_Date = meeting_date
        meeting.Start_Time = start_time
        meeting.GE_Style = ge_style
        meeting.type = meeting_type
        meeting.Meeting_Title = meeting_title
        meeting.Subtitle = subtitle
        meeting.WOD = wod
        meeting.media_id = new_media_id
        # 如果status字段为None，则设置默认值
        if meeting.status is None:
            meeting.status = 'not started'

    # --- 4. Process Agenda Template ---
    SessionLog.query.filter_by(Meeting_Number=meeting_number).delete()

    # Commit the Meeting and Media objects first
    db.session.commit()

    template_path = os.path.join(
        current_app.static_folder, 'mtg_templates', template_file)
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            csv_reader = csv.reader(f)
            first_row = next(csv_reader, None)  # Read the first row

            if first_row:
                # Check if the first row looks like a header by seeing if a SessionType exists for its title
                possible_title = first_row[0].strip()
                if not SessionType.query.filter_by(Title=possible_title).first():
                    # It's likely a header, so we've already consumed it. The loop will start on the next line.
                    pass

            seq = 1
            current_time = start_time
            for row in csv_reader:
                if not row or not row[0].strip():
                    continue

                session_title_from_csv = row[0].strip()
                owner_name = row[1].strip() if len(row) > 1 else ''

                # Handle flexible duration columns
                duration_min = None
                duration_max = None
                # Both min and max are provided
                if len(row) > 3 and row[3].strip():
                    duration_min = row[2].strip() if row[2].strip() else None
                    duration_max = row[3].strip()
                elif len(row) > 2 and row[2].strip():  # Only max is provided
                    duration_max = row[2].strip()

                session_type = SessionType.query.filter_by(
                    Title=session_title_from_csv).first()
                type_id = session_type.id if session_type else None

                if not duration_max and not duration_min and session_type:
                    duration_max = session_type.Duration_Max
                    duration_min = session_type.Duration_Min

                if type_id == 16:  # General Evaluation Report
                    if ge_style == 'Multiple shots':
                        duration_max = 3
                    else:  # 'One shot'
                        duration_max = 5

                break_minutes = 1
                if type_id == 31 and ge_style == 'Multiple shots':  # Individual Evaluation
                    break_minutes += 1

                session_title = session_type.Title if session_type and session_type.Predefined else session_title_from_csv

                owner_id = None
                designation = ''
                if owner_name:
                    owner = Contact.query.filter_by(Name=owner_name).first()
                    if owner:
                        owner_id = owner.id
                        designation = derive_designation(owner)

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
                    dt_current_time = datetime.combine(
                        meeting_date, current_time)
                    next_dt = dt_current_time + \
                        timedelta(minutes=duration_to_add + break_minutes)
                    current_time = next_dt.time()

                db.session.add(new_log)
                seq += 1

            # --- 5. Final Commit ---
            db.session.commit()
    except FileNotFoundError:
        db.session.rollback()  # Rollback changes if template file fails
        return redirect(url_for('agenda_bp.agenda', message=f'Template file not found: {template_file}', category='error'))
    except Exception as e:
        db.session.rollback()  # Rollback on any other error
        return redirect(url_for('agenda_bp.agenda', message=f'Error processing template: {e}', category='error'))

    return redirect(url_for('agenda_bp.agenda', meeting_number=meeting_number))


@agenda_bp.route('/agenda/update', methods=['POST'])
@login_required
def update_logs():
    data = request.get_json()

    meeting_number = data.get('meeting_number')
    agenda_data = data.get('agenda_data', [])
    new_style = data.get('ge_style')
    new_meeting_title = data.get('meeting_title')
    new_meeting_type = data.get('meeting_type')
    new_subtitle = data.get('subtitle')
    new_wod = data.get('wod')
    new_media_url = data.get('media_url')

    if not meeting_number:
        return jsonify(success=False, message="Meeting number is missing"), 400

    try:
        meeting = Meeting.query.filter_by(
            Meeting_Number=meeting_number).first()
        if not meeting:
            return jsonify(success=False, message="Meeting not found"), 404

        if new_meeting_title is not None:
            meeting.Meeting_Title = new_meeting_title

        if new_meeting_type is not None:
            meeting.type = new_meeting_type

        if new_subtitle is not None:
            meeting.Subtitle = new_subtitle

        if new_wod is not None:
            meeting.WOD = new_wod

        new_media_id = None
        if new_media_url:
            existing_media = Media.query.filter_by(url=new_media_url).first()
            if existing_media:
                new_media_id = existing_media.id
            else:
                new_media = Media(url=new_media_url)
                db.session.add(new_media)
                db.session.flush()
                new_media_id = new_media.id

        if new_media_id != meeting.media_id:
            meeting.media_id = new_media_id

        if new_style and meeting.GE_Style != new_style:
            meeting.GE_Style = new_style

        # Commit changes to the meeting object before processing logs
        db.session.commit()

        if new_style:
            # Update the duration for the GE Report session if it exists
            for item in agenda_data:
                # CORRECTED ID: General Evaluation Report is 16
                if str(item.get('type_id')) == '16':
                    if new_style == 'Multiple shots':
                        item['duration_max'] = 3
                    else:  # 'One shot'
                        item['duration_max'] = 5
                    break

        for seq, item in enumerate(agenda_data, 1):
            _create_or_update_session(item, meeting_number, seq)

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