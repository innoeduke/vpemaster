# vpemaster/agenda_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, send_file, current_app
from .auth.utils import login_required
from .models import SessionLog, SessionType, Contact, Meeting, Project, Media, Roster, Role, Vote, Pathway, PathwayProject
from .constants import SessionTypeID, ProjectID
from . import db
from sqlalchemy import distinct, orm, func
from datetime import datetime, timedelta
import io
import csv
import os
import openpyxl
from openpyxl.styles import Font, Alignment
from io import BytesIO
from .utils import load_setting, derive_credentials, get_project_code, get_meetings_by_status, load_all_settings, get_excomm_team
from .tally_sync import sync_participants_to_tally

agenda_bp = Blueprint('agenda_bp', __name__)

# --- Helper Functions for Data Fetching ---

# Table Topics, Prepared Speaker, Pathway Speech, Panel Discussion
# Table Topics, Prepared Speaker, Pathway Speech, Panel Discussion
speech_types_with_project = {
    SessionTypeID.TABLE_TOPICS,
    SessionTypeID.KEYNOTE_SPEECH,
    SessionTypeID.PREPARED_SPEECH,
    SessionTypeID.PANEL_DISCUSSION
}


def _get_agenda_logs(meeting_number):
    """Fetches all agenda logs and related data for a specific meeting."""
    query = db.session.query(SessionLog)\
        .options(
            orm.joinedload(SessionLog.session_type).joinedload(
                SessionType.role),  # Eager load SessionType and Role
            orm.joinedload(SessionLog.meeting),      # Eager load Meeting
            orm.joinedload(SessionLog.project),      # Eager load Project
            # Eager load Owner and associated User
            orm.joinedload(SessionLog.owner).joinedload(Contact.user),
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


def safe_int(val):
    """Safely converts a value to int, handling None, 'null', '', and invalid strings."""
    if val in [None, "", "null", "None"]:
        return None
    try:
        return int(float(val)) # Handle "5.0" strings just in case
    except (ValueError, TypeError):
        return None

def _create_or_update_session(item, meeting_number, seq):
    meeting = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
    if not meeting:
        new_meeting = Meeting(Meeting_Number=meeting_number)
        db.session.add(new_meeting)
        db.session.flush()  # Flush to get meeting ID if needed, though not strictly required here
        meeting = new_meeting

    type_id = safe_int(item.get('type_id'))
    session_type = SessionType.query.get(
        type_id) if type_id else None  # Get the SessionType object

    # --- Owner ID Handling ---
    owner_id = safe_int(item.get('owner_id'))
    # Filter out '0' if that was used as a placeholder for None
    if owner_id == 0: 
        owner_id = None
        
    owner_contact = Contact.query.get(owner_id) if owner_id else None

    # --- Project ID and Status ---
    project_id = safe_int(item.get('project_id'))
    
    status = item.get('status') if item.get('status') else 'Booked'
    session_title = item.get('session_title')

    # --- Credentials Logic (no changes needed) ---
    credentials = item.get('credentials')
    # Check for None or empty string
    if owner_id and (credentials is None or credentials == ''):
        # Use the centralized utility function
        credentials = derive_credentials(owner_contact)

    # --- Automatic project_code Derivation ---
    # RULE: Rely on Project.Format == 'Presentation' for rule enforcement, 
    # since 'Presentation' session type has been removed and all now use 'Prepared Speech'.
    log_project = Project.query.get(project_id) if project_id else None
    is_presentation = log_project is not None and log_project.is_presentation

    if item.get('id') == 'new':
        log_for_derivation = SessionLog(
            Project_ID=project_id,
            Type_ID=type_id,
            Owner_ID=owner_id,
            session_type=session_type,
            project=Project.query.get(project_id) if project_id else None
        )
    else:
        log_for_derivation = SessionLog.query.get(item['id'])
        # Temporarily update for derivation
        log_for_derivation.Project_ID = project_id
        log_for_derivation.Type_ID = type_id
        log_for_derivation.Owner_ID = owner_id
        log_for_derivation.session_type = session_type

    project_code = log_for_derivation.derive_project_code(owner_contact)
        
    # --- Duration Handling ---
    duration_min = safe_int(item.get('duration_min'))
    duration_max = safe_int(item.get('duration_max'))

    # If duration is missing, try to set defaults (Priority: Project > SessionType)
    if duration_min is None and duration_max is None:
        # 1. Project Defaults
        if project_id:
            project_obj = Project.query.get(project_id)
            if project_obj:
                duration_min = project_obj.Duration_Min
                duration_max = project_obj.Duration_Max
        
        # 2. Session Type Defaults (if still None)
        if (duration_min is None and duration_max is None) and session_type:
            # Note: presentation-specific duration defaults now handled via is_presentation check above
            if is_presentation:
                duration_min = 10
                duration_max = 15
            else:
                duration_min = session_type.Duration_Min
                duration_max = session_type.Duration_Max

    # --- Pathway Logic ---
    pathway_val = item.get('pathway')
    
    # RULE: SessionLog.pathway MUST only store pathway-type paths (e.g., "Presentation Mastery").
    # For Presentations, we force use of the owner's main pathway-type path, 
    # even if a "Series" (presentation-type path) was selected in the modal for project lookup.
    if is_presentation:
        if owner_contact and owner_contact.Current_Path:
            pathway_val = owner_contact.Current_Path
    # Fallback for standard sessions if no pathway provided
    elif not pathway_val and owner_contact and owner_contact.Current_Path:
        pathway_val = owner_contact.Current_Path
        
    # --- Create or Update SessionLog ---
    if item['id'] == 'new':
        new_log = SessionLog(
            Meeting_Number=meeting_number,
            Meeting_Seq=seq,
            Type_ID=type_id,
            Owner_ID=owner_id,
            credentials=credentials,
            Duration_Min=duration_min,
            Duration_Max=duration_max,
            Project_ID=project_id,
            Session_Title=session_title,
            Status=status,
            project_code=project_code,
            pathway=pathway_val
        )
        db.session.add(new_log)
    else:
        log = SessionLog.query.get(item['id'])
        if log:
            # Capture old owner ID to detect changes
            old_owner_id = log.Owner_ID
            
            log.Meeting_Number = meeting_number
            log.Meeting_Seq = seq
            log.Type_ID = type_id
            log.Owner_ID = owner_id
            log.credentials = credentials
            log.Duration_Min = duration_min
            log.Duration_Max = duration_max
            log.Project_ID = project_id
            log.Status = status
            if session_title is not None:
                log.Session_Title = session_title
            log.project_code = project_code
            
            # Use log.update_pathway for consistent sync logic
            # Note: For presentations, pathway_val was already potentially overridden to owner.Current_Path above
            if pathway_val:
                log.update_pathway(pathway_val)


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
            # For "Multiple shots" style (ge_mode=1), add an extra minute break after each evaluation
            if log.Type_ID == SessionTypeID.EVALUATION and meeting.ge_mode == 1:
                break_minutes += 1
            dt_current_time = datetime.combine(
                meeting.Meeting_Date, current_time)
            next_dt = dt_current_time + \
                timedelta(minutes=duration_to_add + break_minutes)
            current_time = next_dt.time()

def _get_processed_logs_data(selected_meeting_num):
    """
    Fetches and processes session logs for a given meeting number.
    Returns the list of log dictionaries ready for the frontend.
    """
    selected_meeting = None
    if selected_meeting_num:
        selected_meeting = Meeting.query.options(
            orm.joinedload(Meeting.best_table_topic_speaker),
            orm.joinedload(Meeting.best_evaluator),
            orm.joinedload(Meeting.best_speaker),
            orm.joinedload(Meeting.best_role_taker),
            orm.joinedload(Meeting.media),
            orm.joinedload(Meeting.manager)
        ).filter(Meeting.Meeting_Number == selected_meeting_num).first()

    # Create a simple set of (award_category, contact_id) tuples for quick lookups.
    award_winners = set()
    if selected_meeting:
        if selected_meeting.best_speaker_id:
            award_winners.add(('speaker', selected_meeting.best_speaker_id))
        if selected_meeting.best_evaluator_id:
            award_winners.add(
                ('evaluator', selected_meeting.best_evaluator_id))
        if selected_meeting.best_role_taker_id:
            award_winners.add(
                ('role-taker', selected_meeting.best_role_taker_id))
        if selected_meeting.best_table_topic_id:
            award_winners.add(
                ('table-topic', selected_meeting.best_table_topic_id))

    # --- Fetch Raw Data ---
    raw_session_logs = _get_agenda_logs(selected_meeting_num)
    
    # We also need project speakers for the frontend usually, but this function only returns logs_data.
    # The caller can handle project_speakers separately if needed, or we can return it too.
    # For now, let's keep it focused on logs_data.

    # --- Process Raw Logs into Dictionaries ---
    logs_data = []
    all_pathways = Pathway.query.filter_by(status='active').order_by(Pathway.name).all()
    pathway_mapping = {p.name: p.abbr for p in all_pathways}
    
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
            project = log.project
            if project:
                # Need to find Pathway info (Series)
                pp = PathwayProject.query.filter_by(project_id=project.id).first()
                if pp:
                    pathway_obj = Pathway.query.get(pp.path_id)
                    if pathway_obj:
                         if not session_title_for_dict:
                             session_title_for_dict = project.Project_Name
                         project_name_for_dict = pathway_obj.name # Series Name
                         project_purpose_for_dict = f"Level {pp.level} - {project.Project_Name}"
                         project_code_str = f"{pathway_obj.abbr}{pp.code}"
                         pathway_code_for_dict = pathway_obj.abbr
                         level_for_dict = pp.level
        
        elif log.project and log.project.is_generic:
            project_code_str = "TM1.0"
        elif project:  # Calculate code for any project, even if no owner
            # Use model's resolution logic which includes fallback
            context_path = owner.Current_Path if (owner and owner.Current_Path) else None
            pp, path_obj = project.resolve_context(context_path)
            
            if pp and path_obj and path_obj.abbr:
                project_code_str = f"{path_obj.abbr}{pp.code}"
                pathway_code_for_dict = path_obj.abbr
                
                # Determine level
                if pp.level:
                    level_for_dict = pp.level
                else:
                    try:
                        level_for_dict = int(pp.code.split('.')[0])
                    except (ValueError, IndexError):
                        level_for_dict = None

        # --- Award Logic ---
        award_type = None
        # Simplified award check
        if log.Owner_ID and session_type and session_type.role:
            role_award_category = session_type.role.award_category
            # Check if this role's award category and owner ID exist in the winners set
            if role_award_category and (role_award_category, log.Owner_ID) in award_winners:
                # Format for display (e.g., "Best Speaker")
                award_type = role_award_category.replace('-', ' ').title()

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
            'Credentials': derive_credentials(owner),
            'Duration_Min': log.Duration_Min,
            'Duration_Max': log.Duration_Max,
            'Status': log.Status,
            'project_code': log.project_code,
            # SessionType fields
            'is_section': session_type.Is_Section if session_type else False,
            'session_type_title': session_type.Title if session_type else 'Unknown Type',
            'predefined': session_type.Predefined if session_type else False,
            'is_hidden': session_type.Is_Hidden if session_type else False,
            'role': session_type.role.name if session_type and session_type.role else '',
            'valid_for_project': session_type.Valid_for_Project if session_type else False,
            'pathway': log.pathway, # Explicitly pass current pathway for modal/save sync
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

    # --- Group all "Topics Speaker" sessions after the main "Table Topic Session" ---
    if selected_meeting and selected_meeting.status == 'finished':
        # Find all "Topics Speaker" sessions (Type_ID = 36) and the main TT session (Type_ID = 7)
        topics_speaker_sessions = []
        topics_speaker_indices = []
        tt_session_index = -1

        for i, log in enumerate(logs_data):
            if log['Type_ID'] == SessionTypeID.TOPICS_SPEECH:  # Topics Speaker
                topics_speaker_sessions.append(log)
                topics_speaker_indices.append(i)
            if log['Type_ID'] == SessionTypeID.TABLE_TOPICS:
                tt_session_index = i

        if topics_speaker_sessions and tt_session_index != -1:
            # Identify the winner among the topics speakers
            winner_id = selected_meeting.best_table_topic_id
            if winner_id:
                for session in topics_speaker_sessions:
                    if session['Owner_ID'] == winner_id:
                        # Make the winner's session visible and assign the award
                        session['is_hidden'] = False
                        session['Session_Title'] = 'Best Table Topics Speaker'
                        session['award_type'] = 'table-topic'
                        break  # Found the winner, no need to check further

            # Remove the speaker sessions from their original positions (in reverse to avoid index shifting)
            for i in sorted(topics_speaker_indices, reverse=True):
                logs_data.pop(i)

            # Re-insert the speaker sessions right after the main Table Topic session
            # The insertion index needs to be adjusted based on how many items were removed before it
            final_insert_index = tt_session_index - \
                sum(1 for i in topics_speaker_indices if i < tt_session_index) + 1
            logs_data[final_insert_index:final_insert_index] = topics_speaker_sessions
    
    return logs_data, selected_meeting


# --- Main Route ---


@agenda_bp.route('/agenda', methods=['GET'])
def agenda():
    # --- Determine Selected Meeting ---
    all_meetings = get_meetings_by_status(limit_past=8)

    meeting_numbers = [(m.Meeting_Number, m.Meeting_Date) for m in all_meetings]

    selected_meeting_str = request.args.get('meeting_number')
    selected_meeting_num = None

    if selected_meeting_str:
        try:
            selected_meeting_num = int(selected_meeting_str)
        except ValueError:
            # Handle invalid meeting number string if necessary
            selected_meeting_num = None  # Or redirect, flash error
    else:
        # Priority: Running -> Not Started
        from .utils import get_default_meeting_number
        selected_meeting_num = get_default_meeting_number()

        if selected_meeting_num:
             pass # Found a default
        elif meeting_numbers:
            # Fallback to the most recent existing meeting (highest meeting number)
            selected_meeting_num = meeting_numbers[0][0]

    # --- Use Helper to Get Processed Data ---
    logs_data = []
    selected_meeting = None
    if selected_meeting_num:
        logs_data, selected_meeting = _get_processed_logs_data(selected_meeting_num)
        
        # Security check: Only admins/officers can see unpublished meetings
        if selected_meeting and selected_meeting.status == 'unpublished':
            from flask_login import current_user
            is_manager = current_user.is_authenticated and current_user.Contact_ID == selected_meeting.manager_id
            if not (current_user.is_authenticated and (current_user.is_officer or is_manager)):
                from flask import abort
                abort(403) # Forbidden

    # --- Other Data for Template ---
    project_speakers = _get_project_speakers(selected_meeting_num)
    
    all_pathways = Pathway.query.filter(Pathway.type != 'dummy', Pathway.status == 'active').order_by(Pathway.name).all()
    pathway_mapping = {p.name: p.abbr for p in all_pathways}
    
    pathways = {}
    for p in all_pathways:
        ptype = p.type or "Other"
        if ptype not in pathways:
            pathways[ptype] = []
        pathways[ptype].append(p.name)

    template_dir = os.path.join(current_app.static_folder, 'mtg_templates')
    try:
        meeting_templates = [f for f in os.listdir(
            template_dir) if f.endswith('.csv')]
    except FileNotFoundError:
        meeting_templates = []

    # --- Minimal Data for Initial Page Load ---
    members = Contact.query.filter_by(
        Type='Member').order_by(Contact.Name.asc()).all()

    default_start_time = load_setting(
        'ClubSettings', 'Meeting Start Time', default='18:55')

    # --- Projects for Speech Modal ---
    from .utils import get_dropdown_metadata
    dropdown_data = get_dropdown_metadata()
    
    # --- Render Template ---
    return render_template('agenda.html',
                           logs_data=logs_data,               # Use the processed list of dictionaries
                           pathways=pathways,               # For modals
                           pathway_mapping=pathway_mapping,
                           projects=dropdown_data['projects'],
                           meeting_numbers=meeting_numbers,
                           selected_meeting=selected_meeting,  # Pass the Meeting object
                           members=members,                 # If needed elsewhere
                           project_speakers=project_speakers,  # For JS
                           meeting_templates=meeting_templates,
                           meeting_types=current_app.config['MEETING_TYPES'],
                           default_start_time=default_start_time,
                           GENERIC_PROJECT_ID=ProjectID.GENERIC)


# --- API Endpoints for Asynchronous Data Loading ---

@agenda_bp.route('/api/data/all')
@login_required
def get_all_data_for_modals():
    """
A single endpoint to fetch all data needed for the agenda modals.
    This is called once by the frontend after the initial page load.
    """
    # Session Types
    session_types = SessionType.query.options(orm.joinedload(
        SessionType.role)).order_by(SessionType.Title.asc()).all()
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
            "Credentials": derive_credentials(c),
            "Current_Path": c.Current_Path,
            "Next_Project": c.Next_Project
        } for c in contacts
    ]

    # Projects
    projects = Project.query.order_by(Project.Project_Name).all()

    all_pp = db.session.query(PathwayProject, Pathway.abbr).join(Pathway).all()
    project_codes_lookup = {}  # {project_id: {path_abbr: {'code': code, 'level': level}, ...}}
    for pp, path_abbr in all_pp:
        if pp.project_id not in project_codes_lookup:
            project_codes_lookup[pp.project_id] = {}
        project_codes_lookup[pp.project_id][path_abbr] = {'code': pp.code, 'level': pp.level}

    projects_data = [
        {
            "id": p.id, "Project_Name": p.Project_Name,
            "path_codes": project_codes_lookup.get(p.id, {}),
            "Purpose": p.Purpose, "Duration_Min": p.Duration_Min, "Duration_Max": p.Duration_Max
        } for p in projects
    ]

    # Meeting Roles (Constructed from DB for backward compatibility with frontend keys)
    # We use name.upper().replace(' ', '_') to match the legacy Config.ROLES keys where possible.
    roles_from_db = Role.query.all()
    meeting_roles_data = {}
    for r in roles_from_db:
        role_key = r.name.upper().replace(' ', '_').replace('-', '_')
        meeting_roles_data[role_key] = {
            "name": r.name,
            "icon": r.icon,
            "type": r.type,
            "award": r.award_category,
            "unique": r.is_distinct # Map database is_distinct to legacy 'unique' property
        }

    # Fetch Series Initials from DB
    pathways_db = Pathway.query.filter_by(status='active').all()
    series_initials_db = {p.name: p.abbr for p in pathways_db if p.abbr}

    return jsonify({
        'session_types': session_types_data,
        'contacts': contacts_data,
        'projects': projects_data,
        'series_initials': series_initials_db,
        'meeting_types': current_app.config['MEETING_TYPES'],
        'meeting_roles': meeting_roles_data
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
     .outerjoin(Project, SessionLog.Project_ID == Project.id)\
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
    speech_session_type_ids = {
        SessionTypeID.TABLE_TOPICS,
        SessionTypeID.KEYNOTE_SPEECH,
        SessionTypeID.PREPARED_SPEECH,
        SessionTypeID.PANEL_DISCUSSION
    }
    presentation_session_type_id = SessionTypeID.PRESENTATION

    for log, session_type, contact, project, media in logs_data:
        if not log.Project_ID or not session_type:
            continue

        details_to_add = None

        # Handle Pathway Speech types and Presentation
        if session_type.id in speech_session_type_ids.union({presentation_session_type_id}) and project:
            if project.is_generic:  # Generic Project
                pathway_name = "Generic"
                pathway_project_code = "1.0"
                pathway_obj = None
                pp = None
                proj_code = "TM1.0"
            else:
                context_path = contact.Current_Path if contact else None
                pp, pathway_obj = project.resolve_context(context_path)
                
                if pathway_obj:
                    pathway_name = pathway_obj.name
                    pathway_project_code = pp.code if pp else None
                    proj_code = f"{pathway_obj.abbr}{pp.code}" if pp else ""
                else:
                    pathway_name = context_path or ""
                    pathway_project_code = None
                    proj_code = ""

            # Determine project purpose string
            # Prioritize the Purpose field from the DB if available
            if project.Purpose:
                project_purpose = project.Purpose
            elif pp and pp.level:
                 project_purpose = f"Level {pp.level} - {project.Project_Name}"
            else:
                 project_purpose = ""

            # Use project duration from DB
            duration_str = f"[{project.Duration_Min}'-{project.Duration_Max}']"
            # Legacy presentation logic hardcoded [10'-15'], but DB should be source of truth.

            details_to_add = {
                "speech_title": log.Session_Title or project.Project_Name,
                "project_name": project.Project_Name,
                "pathway_name": pathway_name,
                "project_purpose": project_purpose,
                "project_code": proj_code,
                "duration": duration_str,
                "project_type": _get_project_type(pathway_project_code)
            }

        if details_to_add:
            speeches.append(details_to_add)

    return speeches


def _format_export_row(log, session_type, contact, project, pathway_mapping):
    """Formats a single row for the human-readable agenda (Sheet 1)."""
    if session_type and session_type.Is_Section:
        return ('section', ['', log.Session_Title or session_type.Title, '', ''])

    start_time = log.Start_Time.strftime('%H:%M') if log.Start_Time else ''

    session_title_str = log.Session_Title or (
        session_type.Title if session_type else '')
    project_code_str = None

    if log.project and log.project.is_generic:
        project_code_str = "TM1.0"
        if not log.Session_Title and project:
            session_title_str = project.Project_Name

    # Check for Pathway Speech (Type 30) or Presentation (Type 43)
    if session_type and session_type.id in [SessionTypeID.PREPARED_SPEECH, SessionTypeID.PRESENTATION] and project:
        # Use simple get_code which includes fallback logic
        path_name = contact.Current_Path if contact else None
        code = project.get_code(path_name)
        if code:
            project_code_str = code
        
        if not log.Session_Title:  # If title is blank, use project name
            session_title_str = project.Project_Name

    # Check for Individual Evaluator (Type 31)
    if session_type and session_type.id == SessionTypeID.EVALUATION and log.Session_Title:
        speaker_name = log.Session_Title
        speaker = Contact.query.filter_by(Name=speaker_name).first()
        if speaker and speaker.DTM:
            speaker_name += '\u1D30\u1D40\u1D39'
        session_title_str = f"Evaluator for {speaker_name}"

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
        if log.credentials and not contact.DTM:
            meta_parts.append(log.credentials)
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
            f"{entry.ticket} ({entry.contact.Type})"
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
    # (Keynote/Master contact determination based on owner_role_id was removed)

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
        meeting.best_table_topic_speaker.Name if meeting.best_table_topic_speaker else "",
        meeting.best_role_taker.Name if meeting.best_role_taker else "",
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
        # Get project code if available - using the helper function
        project_code_str = ""
        context_path = contact.Current_Path if contact else None
        if proj:
             code = proj.get_code(context_path)
             if code:
                 project_code_str = code

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
        orm.joinedload(Meeting.best_table_topic_speaker),
        orm.joinedload(Meeting.best_evaluator),
        orm.joinedload(Meeting.best_speaker),
        orm.joinedload(Meeting.best_role_taker),
        orm.joinedload(Meeting.media)
    ).filter_by(Meeting_Number=meeting_number).first()
    if not meeting:
        return "Meeting not found", 404

    # 1. Fetch and Prepare Data
    all_pathways = Pathway.query.filter_by(status='active').order_by(Pathway.name).all()
    pathway_mapping = {p.name: p.abbr for p in all_pathways}
    logs_data = _get_export_data(meeting_number)
    speech_details_list = _get_all_speech_details(logs_data, pathway_mapping)

    # 2. Create Workbook and Sheets
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws2 = wb.create_sheet(title="PowerBI Data")
    ws3 = wb.create_sheet(title="Roster")
    ws4 = wb.create_sheet(title="Participants")

    # 3. Build Sheets
    _build_sheet1(ws1, logs_data, speech_details_list, pathway_mapping)
    _build_sheet2_powerbi(ws2, meeting, logs_data,
                          speech_details_list, pathway_mapping)
    _build_sheet3_roster(ws3, meeting_number)
    _build_sheet4_participants(ws4, logs_data)

    # 4. Save and Send
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    filename = f"Agenda_{meeting.Meeting_Date.strftime('%Y-%m-%d')}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


def _get_participants_dict(logs_data):
    """
    Extracts participant data for Sheet 4 and Tally Sync.
    Returns a dictionary of group_name -> list of strings (names or "Role: Name").
    """
    # sets to track unique participants per group
    prepared_speakers = set()
    evaluators = set()
    tt_speakers = set()
    # For role takers, we store (Role Name, Participant Name) tuples to sort/deduplicate
    role_takers = set()

    # IDs for classification
    # Prepared Speakers: 20 (Panelist), 30 (Pathway Speech), 43 (Presentation), 44 (Social Speech)
    # AND Project must be valid (not None) for it to be a speaker role usually,
    # but the sheet 4 logic specifically checks for these types.
    # Note: Logic copied from original _build_sheet4_participants
    speaker_types = {20, 30, 43, 44}
    
    # Individual Evaluators: 31
    evaluator_type = 31

    # Table Topics: 7 (Table Topics Speaker) - typically handled specifically if needed
    tt_type = 36 # Changed from 7 to 36 to match original logic (Topics Speaker)

    for log, session_type, contact, project, media in logs_data:
        # Check if we have a valid contact (the person performing the role)
        if not contact or not contact.Name:
            continue
            
        name = contact.Name.strip()
        if not name:
            continue
            
        if not session_type:
            continue

        # Add (Guest) tag if applicable
        display_name = name
        if contact.Type == 'Guest':
            display_name = f"{name} (Guest)"

        st_id = session_type.id
        
        # 1. Prepared Speakers
        if st_id in speaker_types:
             prepared_speakers.add(display_name)
             
        # 2. Individual Evaluators
        elif st_id == evaluator_type:
             evaluators.add(display_name)
             
        # 3. Table Topics
        elif st_id == tt_type:
             tt_speakers.add(display_name)
             
        # 4. Role Takers (Everything else that is a role)
        # Excluding Section headers (Is_Section is True) or Hidden items if desired?
        # The original code logic:
        # if st_id not in speaker_types and st_id != evaluator_type and st_id != tt_type:
        #    ...
        elif not session_type.Is_Section and not session_type.Is_Hidden:
            # Assume it's a role taker if it's not one of the above special categories
            # and is a visible role.
            # Original code also excluded officer roles: if session_type.role and session_type.role.type == 'officer': continue
            # Re-adding that logic here.
            if session_type.role and session_type.role.type == 'officer':
                continue

            # Use Session Title or Session Type Title as the Role Name?
            # Original code used: role_name = session_type.Title or session_type.role.name
            role_name = session_type.Title
            if session_type.role:
                role_name = session_type.role.name
            
            if role_name:
                role_takers.add((role_name.strip(), display_name))

    return {
        "Prepared Speakers": sorted(list(prepared_speakers)),
        "Individual Evaluators": sorted(list(evaluators)),
        "Table Topics Speakers": sorted(list(tt_speakers)),
        "Role Takers": sorted(list(role_takers), key=lambda x: (x[0], x[1]))
    }


def write_group(group_name, names_list, ws):
    if not names_list:
        return
    for name in names_list:
        ws.append([group_name, name])


def _build_sheet4_participants(ws, logs_data):
    """Populates Sheet 4 (Participants) of the workbook."""
    ws.title = "Participants"
    ws.append(['Group', 'Name'])
    for cell in ws[1]:
        cell.font = Font(bold=True)

    data = _get_participants_dict(logs_data)
    
    write_group("Prepared Speakers", data["Prepared Speakers"], ws)
    if data["Prepared Speakers"]: ws.append([])
    
    write_group("Individual Evaluators", data["Individual Evaluators"], ws)
    if data["Individual Evaluators"]: ws.append([])
    
    # Write Role Takers
    role_takers = data["Role Takers"]
    if role_takers:
        for role, name in role_takers:
            ws.append([role, name])
        ws.append([])
        
    write_group("Table Topics Speakers", data["Table Topics Speakers"], ws)

    _auto_fit_worksheet_columns(ws, min_width=15)


def _validate_meeting_form_data(form):
    """Parses and validates meeting form data."""
    meeting_number = form.get('meeting_number')
    meeting_type = form.get('meeting_type')
    
    # Check template validity
    meeting_types_dict = current_app.config.get('MEETING_TYPES', {})
    template_file = meeting_types_dict.get(meeting_type, {}).get('template')
    if not template_file:
         raise ValueError(f"Invalid meeting type: {meeting_type}")

    meeting_date_str = form.get('meeting_date')
    start_time_str = form.get('start_time')
    try:
        meeting_date = datetime.strptime(meeting_date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
    except (ValueError, TypeError):
         raise ValueError("Invalid date or time format.")

    return {
        'meeting_number': meeting_number,
        'meeting_date': meeting_date,
        'start_time': start_time,
        'meeting_type': meeting_type,
        'ge_mode': int(form.get('ge_mode', 0)),
        'meeting_title': form.get('meeting_title'),
        'subtitle': form.get('subtitle'),
        'wod': form.get('wod'),
        'media_url': form.get('media_url'),
        'template_file': template_file
    }


def _get_or_create_media_id(media_url):
    """Finds existing media or creates new one, returning the ID."""
    if not media_url:
        return None
        
    existing_media = Media.query.filter_by(url=media_url).first()
    if existing_media:
        return existing_media.id
    
    new_media = Media(url=media_url)
    db.session.add(new_media)
    db.session.flush()
    return new_media.id


def _upsert_meeting_record(data, media_id):
    """Creates or updates the Meeting record."""
    meeting = Meeting.query.filter_by(Meeting_Number=data['meeting_number']).first()
    if not meeting:
        meeting = Meeting(
            Meeting_Number=data['meeting_number'],
            Meeting_Date=data['meeting_date'],
            Start_Time=data['start_time'],
            ge_mode=data['ge_mode'],
            type=data['meeting_type'],
            Meeting_Title=data['meeting_title'],
            Subtitle=data['subtitle'],
            WOD=data['wod'],
            media_id=media_id,
            status='unpublished'
        )
        db.session.add(meeting)
    else:
        meeting.Meeting_Date = data['meeting_date']
        meeting.Start_Time = data['start_time']
        meeting.ge_mode = data['ge_mode']
        meeting.type = data['meeting_type']
        meeting.Meeting_Title = data['meeting_title']
        meeting.Subtitle = data['subtitle']
        meeting.WOD = data['wod']
        meeting.media_id = media_id
        if meeting.status is None:
            meeting.status = 'unpublished'
    return meeting


def _generate_logs_from_template(meeting, template_file):
    """Reads the CSV template and generates session logs."""
    # Clear existing logs
    SessionLog.query.filter_by(Meeting_Number=meeting.Meeting_Number).delete()
    
    template_path = os.path.join(
        current_app.static_folder, 'mtg_templates', template_file)
        
    # Pre-load settings for efficiency
    all_settings = load_all_settings()
    excomm_team = get_excomm_team(all_settings)

    with open(template_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader, None)  # Skip Header Row
        
        seq = 1
        current_time = meeting.Start_Time

        for row in reader:
            # Skip perfectly empty rows
            if not any(cell.strip() for cell in row):
                continue

            # Parse row columns safely
            def get_col(idx):
                return row[idx].strip() if idx < len(row) and row[idx].strip() else None

            type_val = get_col(0)
            title_val = get_col(1)
            role_val = get_col(2)
            owner_val = get_col(3)
            min_val = get_col(4)
            max_val = get_col(5)

            # --- Resolve Session Type ---
            session_type = None
            type_id = 8  # Default to 'Custom Session' (ID 8)
            if type_val:
                session_type = SessionType.query.filter_by(Title=type_val).first()
                if session_type:
                    type_id = session_type.id
            
            # --- Resolve Session Title ---
            session_title_for_log = title_val
            if not session_title_for_log and session_type and session_type.Predefined:
                    session_title_for_log = session_type.Title

            # --- Resolve Durations ---
            def local_safe_int(v):
                try: return int(v) if v else None
                except ValueError: return None

            duration_min = local_safe_int(min_val)
            duration_max = local_safe_int(max_val)

            if duration_min is None and duration_max is None and session_type:
                duration_min = session_type.Duration_Min
                duration_max = session_type.Duration_Max

            # Special Logic for GE styles
            if type_id == 16:  # General Evaluation Report
                if meeting.ge_mode == 1: # Distributed
                    duration_max = 3
                else:  # 0: Traditional
                    duration_max = 5
            
            break_minutes = 1
            if type_id == 31 and meeting.ge_mode == 1:  # Individual Evaluation
                break_minutes += 1

            # --- Resolve Owner ---
            owner_id = None
            credentials = ''
            if owner_val:
                owner = Contact.query.filter_by(Name=owner_val).first()
                if owner:
                    owner_id = owner.id
                    credentials = derive_credentials(owner)
            
            # Auto-populate from Excomm Team if owner is missing
            if not owner_id:
                role_to_check = role_val
                if not role_to_check and session_type and session_type.role:
                        role_to_check = session_type.role.name
                
                if role_to_check:
                        officer_name = excomm_team['members'].get(role_to_check)
                        if officer_name:
                            owner = Contact.query.filter_by(Name=officer_name).first()
                            if owner:
                                owner_id = owner.id
                                credentials = derive_credentials(owner)
            
            # --- Create Log ---
            new_log = SessionLog(
                Meeting_Number=meeting.Meeting_Number,
                Meeting_Seq=seq,
                Type_ID=type_id,
                Owner_ID=owner_id,
                credentials=credentials,
                Duration_Min=duration_min,
                Duration_Max=duration_max,
                Session_Title=session_title_for_log,
                Status='Booked'
            )

            # Calculate Start Time
            is_section = False
            if session_type and session_type.Is_Section:
                is_section = True
            
            if not is_section:
                new_log.Start_Time = current_time
                # Calculate next start time
                dur_to_add = int(duration_max or 0)
                dt_current = datetime.combine(meeting.Meeting_Date, current_time)
                next_dt = dt_current + timedelta(minutes=dur_to_add + break_minutes)
                current_time = next_dt.time()
            else:
                new_log.Start_Time = None

            db.session.add(new_log)
            seq += 1


@agenda_bp.route('/agenda/create', methods=['POST'])
@login_required
def create_from_template():
    try:
        # 1. Validation & Data Extraction
        data = _validate_meeting_form_data(request.form)
    except ValueError as e:
        return redirect(url_for('agenda_bp.agenda', message=str(e), category='error'))

    try:
        # 2. Handle Media
        media_id = _get_or_create_media_id(data['media_url'])

        # 3. Create or Update Meeting
        meeting = _upsert_meeting_record(data, media_id)
        
        # Commit to ensure Meeting exists and has proper state before logs are created
        db.session.commit()

        # 4. Generate Session Logs from Template
        _generate_logs_from_template(meeting, data['template_file'])
        
        # Final Commit
        db.session.commit()
        
        return redirect(url_for('agenda_bp.agenda', meeting_number=data['meeting_number'], message='Meeting created successfully from template!', category='success'))

    except FileNotFoundError:
        return redirect(url_for('agenda_bp.agenda', message='Template file not found.', category='error'))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating meeting: {e}")
        return redirect(url_for('agenda_bp.agenda', message=f'Error processing template: {str(e)}', category='error'))



@agenda_bp.route('/agenda/update', methods=['POST'])
@login_required
def update_logs():
    data = request.get_json()

    meeting_number = data.get('meeting_number')
    agenda_data = data.get('agenda_data', [])
    new_mode = int(data.get('ge_mode', 0)) if data.get('ge_mode') is not None else None
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

        # Update Manager
        new_manager_id = data.get('manager_id')
        if new_manager_id == "":
            meeting.manager_id = None
        elif new_manager_id:
             try:
                 meeting.manager_id = int(new_manager_id)
             except ValueError:
                 pass # Ignore invalid ID

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

        if new_mode is not None and meeting.ge_mode != new_mode:
            meeting.ge_mode = new_mode

        # Commit changes to the meeting object before processing logs
        db.session.commit()

        if new_mode is not None:
            # Update the duration for the GE Report session if it exists
            for item in agenda_data:
                # CORRECTED ID: General Evaluation Report is 16
                if str(item.get('type_id')) == '16':
                    if new_mode == 1:
                        item['duration_max'] = 3
                    else:  # 0
                        item['duration_max'] = 5
                    break

        for seq, item in enumerate(agenda_data, 1):
            _create_or_update_session(item, meeting_number, seq)

        _recalculate_start_times([meeting])

        # Commit the final session and time changes.
        db.session.commit()

        # Fetch fresh data for client-side update
        logs_data, _ = _get_processed_logs_data(meeting_number)
        project_speakers = _get_project_speakers(meeting_number)

        return jsonify(success=True, logs_data=logs_data, project_speakers=project_speakers)
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


def _tally_votes_and_set_winners(meeting):
    """
    Tallies votes for a given meeting and sets the best award winners.
    """
    if not meeting:
        return

    # Query to get all vote counts grouped by category and contact
    vote_counts = db.session.query(
        Vote.award_category,
        Vote.contact_id,
        func.count(Vote.id).label('vote_count')
    ).filter(Vote.meeting_number == meeting.Meeting_Number)\
     .group_by(Vote.award_category, Vote.contact_id)\
     .all()

    # Process votes for each category
    winners = {}  # {'speaker': (contact_id, vote_count), ...}
    for category, contact_id, count in vote_counts:
        if category not in winners or count > winners[category][1]:
            winners[category] = (contact_id, count)
        # Simple tie-breaking: first one with max votes wins.

    # Update meeting object with winners
    for category, (winner_id, _) in winners.items():
        award_attr = f"best_{category.replace('-', '_')}_id"
        if hasattr(meeting, award_attr):
            setattr(meeting, award_attr, winner_id)


@agenda_bp.route('/agenda/status/<int:meeting_number>', methods=['POST'])
@login_required
def update_meeting_status(meeting_number):
    """Toggles the status of a meeting."""
    meeting = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
    if not meeting:
        return jsonify(success=False, message="Meeting not found"), 404

    current_status = meeting.status
    new_status = current_status

    if current_status == 'unpublished':
        new_status = 'not started'
    elif current_status == 'not started':
        new_status = 'running'
    elif current_status == 'running':
        new_status = 'finished'
        # Tally votes when meeting finishes
        _tally_votes_and_set_winners(meeting)
    elif current_status == 'finished':
        # Full deletion flow as requested
        try:
            # 1. Delete Waitlist entries associated with this meeting's session logs
            session_log_ids = [log.id for log in meeting.session_logs]
            if session_log_ids:
                from .models import Waitlist
                Waitlist.query.filter(Waitlist.session_log_id.in_(session_log_ids)).delete(synchronize_session=False)

            # 2. Delete SessionLog entries (cascades to Media via models.py definition)
            for log in meeting.session_logs:
                db.session.delete(log)

            # 3. Delete Vote entries
            from .models import Vote
            Vote.query.filter_by(meeting_number=meeting_number).first()
            Vote.query.filter_by(meeting_number=meeting_number).delete(synchronize_session=False)

            # 4. Handle Meeting's Media
            if meeting.media_id:
                media_to_delete = meeting.media
                meeting.media_id = None # Break the link first
                db.session.delete(media_to_delete)

            # 5. Delete the Meeting itself
            db.session.delete(meeting)
            db.session.commit()
            return jsonify(success=True, deleted=True)
        except Exception as e:
            db.session.rollback()
            return jsonify(success=False, message=f"Deletion failed: {str(e)}"), 500

    meeting.status = new_status

    try:
        db.session.commit()
        return jsonify(success=True, new_status=new_status)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@agenda_bp.route('/agenda/sync_tally/<int:meeting_number>', methods=['POST'])
@login_required
def sync_tally(meeting_number):
    try:
        logs_data = _get_export_data(meeting_number)
        participants_dict = _get_participants_dict(logs_data)
        sync_participants_to_tally(participants_dict)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500
