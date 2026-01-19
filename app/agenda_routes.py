# vpemaster/agenda_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, send_file, current_app, flash
from flask_login import current_user
from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
from .models import SessionLog, SessionType, Contact, Meeting, Project, Media, Roster, MeetingRole, Vote, Pathway, PathwayProject
from .constants import SessionTypeID, ProjectID, SPEECH_TYPES_WITH_PROJECT
from .services.export import MeetingExportService
from .services.export.context import MeetingExportContext
from . import db
from sqlalchemy import distinct, orm, func
from datetime import datetime, timedelta
import io
import csv
import os
import openpyxl
from openpyxl.styles import Font, Alignment
from io import BytesIO
from .utils import derive_credentials, get_project_code, get_meetings_by_status
from .tally_sync import sync_participants_to_tally
from .services.role_service import RoleService
from .club_context import get_current_club_id, filter_by_club, authorized_club_required
from .models import ContactClub

agenda_bp = Blueprint('agenda_bp', __name__)

# --- Helper Functions for Data Fetching ---

# Table Topics, Prepared Speaker, Pathway Speech, Panel Discussion


def _get_agenda_logs(meeting_number):
    """Fetches all agenda logs and related data for a specific meeting."""
    query = db.session.query(SessionLog)\
        .options(
            orm.joinedload(SessionLog.session_type).joinedload(
                SessionType.role),  # Eager load SessionType and Role
            orm.joinedload(SessionLog.meeting),      # Eager load Meeting
            orm.joinedload(SessionLog.project),      # Eager load Project
            # Eager load Owner and associated User
            orm.joinedload(SessionLog.owner),
            orm.joinedload(SessionLog.media)
    )

    if meeting_number:
        query = query.filter(SessionLog.Meeting_Number == meeting_number)

    # Order by sequence
    logs = query.order_by(SessionLog.Meeting_Seq.asc()).all()
    owners = [log.owner for log in logs if log.owner]
    if owners:
        from .club_context import get_current_club_id
        Contact.populate_users(owners, get_current_club_id())
    return logs


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
    session_type = db.session.get(SessionType, type_id) if type_id else None

    # --- Owner ID Handling ---
    owner_id = safe_int(item.get('owner_id'))
    # Filter out '0' if that was used as a placeholder for None
    if owner_id == 0: 
        owner_id = None
        
    owner_contact = db.session.get(Contact, owner_id) if owner_id else None

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
    log_project = db.session.get(Project, project_id) if project_id else None
    is_presentation = log_project is not None and log_project.is_presentation

    if item.get('id') == 'new':
        log_for_derivation = SessionLog(
            Project_ID=project_id,
            Type_ID=type_id,
            Owner_ID=owner_id,
            session_type=session_type,
            project=db.session.get(Project, project_id) if project_id else None
        )
    else:
        log_for_derivation = db.session.get(SessionLog, item['id'])
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
            project_obj = db.session.get(Project, project_id)
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
    # Create valid log object first (Owner_ID will be handled by assign_role_owner if needed)
    if item['id'] == 'new':
        new_log = SessionLog(
            Meeting_Number=meeting_number,
            Meeting_Seq=seq,
            Type_ID=type_id,
            Owner_ID=owner_id, # Set initially, but assign_role_owner will handle logic
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
        log = new_log
        old_owner_id = None
        old_role = None
    else:
        log = db.session.get(SessionLog, item['id'])
        if log:
            # Capture old state for roster sync
            old_owner_id = log.Owner_ID
            old_role = log.session_type.role if log.session_type and log.session_type.role else None
            
            log.Meeting_Number = meeting_number
            log.Meeting_Seq = seq
            # log.Type_ID = type_id # Defer update to handle role changes
            
            log.Duration_Min = duration_min
            log.Duration_Max = duration_max
            log.Project_ID = project_id
            log.Status = status
            if session_title is not None:
                log.Session_Title = session_title
            
            # Use log.update_pathway for consistent sync logic
            if pathway_val:
                log.update_pathway(pathway_val)

    # Use shared assignment logic if owner changed or it's a new log with an owner
    if log:
        new_role = session_type.role if session_type else None
        
        role_changed = (old_role != new_role)
        owner_changed = (old_owner_id != owner_id)
        
        if role_changed or owner_changed:
            if item['id'] != 'new' and old_owner_id and old_role and role_changed:
                # Force unassign from the OLD role if the type changed
                Roster.sync_role_assignment(log.Meeting_Number, old_owner_id, old_role, 'unassign')
            
            # Update role type before calling assignment logic 
            log.Type_ID = type_id
            RoleService.assign_meeting_role(log, owner_id, is_admin=True)
        else:
            # Ensure fields are set if NOT calling RoleService (which does this internally)
            log.Owner_ID = owner_id
            log.credentials = credentials
            log.project_code = project_code



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
    club_id = get_current_club_id()
    if selected_meeting_num:
        query = Meeting.query.options(
            orm.joinedload(Meeting.best_table_topic_speaker),
            orm.joinedload(Meeting.best_evaluator),
            orm.joinedload(Meeting.best_speaker),
            orm.joinedload(Meeting.best_role_taker),
            orm.joinedload(Meeting.media),
            orm.joinedload(Meeting.manager)
        ).filter(Meeting.Meeting_Number == selected_meeting_num)
        if club_id:
            query = query.filter(Meeting.club_id == club_id)
        selected_meeting = query.first()

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

    # --- Pre-fetch Pathway Project Data for current meeting logs ---
    project_ids = [log.Project_ID for log in raw_session_logs if log.Project_ID]
    pp_cache = Project.prefetch_context(project_ids)
    
    # Pre-fetch potential speakers for DTM check (Evaluation logs)
    evaluator_speaker_names = [
        log.Session_Title for log in raw_session_logs 
        if log.session_type and log.session_type.Title == 'Evaluation' and log.Session_Title
    ]
    
    speaker_dtm_cache = {}
    if evaluator_speaker_names:
        speakers = Contact.query.filter(Contact.Name.in_(evaluator_speaker_names)).all()
        for s in speakers:
            speaker_dtm_cache[s.Name] = s.DTM

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
                # Need to find Pathway info (Series) -> Use Cache
                pp, pathway_obj = Project.resolve_context_from_cache(log.Project_ID, None, pp_cache)
                
                if pp and pathway_obj:
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
            
            # OPTIMIZED: Use memory cache via Model Method
            pp, path_obj = Project.resolve_context_from_cache(log.Project_ID, context_path, pp_cache)
            
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
            if log.Session_Title in speaker_dtm_cache and speaker_dtm_cache[log.Session_Title]:
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
            'owner_club': owner.get_primary_club().club_name if (owner and owner.get_primary_club()) else '',
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
@authorized_club_required
def agenda():
    # --- Handle Club Context for Guests ---
    club_id_param = request.args.get('club_id')
    if club_id_param:
        try:
            from .club_context import set_current_club_id
            set_current_club_id(int(club_id_param))
        except (ValueError, TypeError):
            pass

    # --- Determine Selected Meeting ---
    all_meetings, _ = get_meetings_by_status(limit_past=8)

    meeting_numbers = [(m.Meeting_Number, m.Meeting_Date, m.status) for m in all_meetings]

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
        
        if not selected_meeting:
             # Handle meeting not found (deleted or invalid number)
             flash(f"Meeting #{selected_meeting_num} not found or you don't have access.", "warning")
             return redirect(url_for('agenda_bp.agenda'))

        # Custom Security Check based on Status
        # 1. Unpublished: Only Officers/Admin can view full details
        if selected_meeting.status == 'unpublished':
            if not is_authorized(Permissions.VOTING_VIEW_RESULTS, meeting=selected_meeting):
                # Unauthorized users cannot view unpublished meetings
                # Redirect to generic not-started page
                return redirect(url_for('agenda_bp.meeting_notice', meeting_number=selected_meeting_num))

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

    # --- Template Data ---
    # We use the mapping defined in the Meeting model as the source of truth
    meeting_types = Meeting.TYPE_TO_TEMPLATE

    # --- Minimal Data for Initial Page Load ---
    club_id = get_current_club_id()
    members = Contact.query.join(ContactClub).filter(
        ContactClub.club_id == club_id,
        Contact.Type == 'Member'
    ).order_by(Contact.Name.asc()).all()

    # Default meeting start time (can be overridden by Club model if needed)
    default_start_time = '18:55'

    # Calculate next meeting number and suggested date
    next_meeting_num = db.session.query(func.max(Meeting.Meeting_Number)).filter(Meeting.club_id == club_id).scalar()
    next_meeting_num = (next_meeting_num or 0) + 1
    
    # Suggest next meeting date (last meeting + 7 days, or today)
    last_meeting = Meeting.query.filter_by(club_id=club_id).order_by(Meeting.Meeting_Date.desc()).first()
    if last_meeting and last_meeting.Meeting_Date:
        next_meeting_date = (last_meeting.Meeting_Date + timedelta(days=7)).strftime('%Y-%m-%d')
    else:
        next_meeting_date = datetime.now().strftime('%Y-%m-%d')

    # --- Projects for Speech Modal ---
    from .utils import get_dropdown_metadata
    dropdown_data = get_dropdown_metadata()
    
    # --- Render Template ---
    # Serialize ProjectID as a dictionary for safe JSON conversion in template
    project_id_dict = {
        'GENERIC': ProjectID.GENERIC,
        'TOPICSMASTER_PROJECT': ProjectID.TOPICSMASTER_PROJECT,
        'KEYNOTE_SPEAKER_PROJECT': ProjectID.KEYNOTE_SPEAKER_PROJECT,
        'MODERATOR_PROJECT': ProjectID.MODERATOR_PROJECT,
        'EVALUATION_PROJECTS': ProjectID.EVALUATION_PROJECTS
    }
    
    return render_template('agenda.html',
                           logs_data=logs_data,               # Use the processed list of dictionaries
                           pathways=pathways,               # For modals
                           pathway_mapping=pathway_mapping,
                           projects=dropdown_data['projects'],
                           meeting_numbers=meeting_numbers,
                           selected_meeting=selected_meeting,  # Pass the Meeting object
                           members=members,                 # If needed elsewhere
                           project_speakers=project_speakers,  # For JS
                           meeting_types=meeting_types,
                           default_start_time=default_start_time,
                           next_meeting_num=next_meeting_num,
                           next_meeting_date=next_meeting_date,
                           ProjectID=project_id_dict)


@agenda_bp.route('/meeting-notice/<int:meeting_number>')
def meeting_notice(meeting_number):
    """Generic meeting notice page for unauthorized access."""
    meeting = Meeting.query.filter_by(Meeting_Number=meeting_number).first()
    status = meeting.status if meeting else 'unknown'
    return render_template('meeting_notice.html', meeting_number=meeting_number, meeting_status=status)


# --- API Endpoints for Asynchronous Data Loading ---

@agenda_bp.route('/api/data/all')
@login_required
@authorized_club_required
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
    club_id = get_current_club_id()
    contacts = Contact.query.join(ContactClub).filter(ContactClub.club_id == club_id)\
        .order_by(Contact.Name.asc()).all()
    
    Contact.populate_users(contacts, club_id)
    
    contacts_data = [
        {
            "id": c.id, "Name": c.Name, "DTM": c.DTM, "Type": c.Type,
            "Club": c.get_primary_club().club_name if c.get_primary_club() else '', 
            "Completed_Paths": c.Completed_Paths,
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
    roles_from_db = MeetingRole.query.all()
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
    
    # Pathways grouped by type
    pathways_grouped = {}
    for p in pathways_db:
        ptype = p.type or "Other"
        if ptype not in pathways_grouped:
            pathways_grouped[ptype] = []
        pathways_grouped[ptype].append(p.name)
    
    # Pathway mapping
    pathway_mapping = {p.name: p.abbr for p in pathways_db}

    return jsonify({
        'session_types': session_types_data,
        'contacts': contacts_data,
        'projects': projects_data,
        'series_initials': series_initials_db,
        'meeting_roles': meeting_roles_data,
        'pathways': pathways_grouped,
        'pathway_mapping': pathway_mapping,
        'project_id_constants': {
            'GENERIC': ProjectID.GENERIC,
            'TOPICSMASTER_PROJECT': ProjectID.TOPICSMASTER_PROJECT,
            'KEYNOTE_SPEAKER_PROJECT': ProjectID.KEYNOTE_SPEAKER_PROJECT,
            'MODERATOR_PROJECT': ProjectID.MODERATOR_PROJECT,
            'EVALUATION_PROJECTS': ProjectID.EVALUATION_PROJECTS
        }
    })




@agenda_bp.route('/agenda/export/<int:meeting_number>')
@login_required
@authorized_club_required
def export_agenda(meeting_number):
    """
    Generates a multi-sheet XLSX export of the agenda using the ExportService.
    """
    output = MeetingExportService.generate_meeting_xlsx(meeting_number)
    if not output:
        return "Meeting not found", 404

    # Fetch meeting for filename
    meeting = db.session.get(Meeting, meeting_number) or Meeting.query.filter_by(Meeting_Number=meeting_number).first()
    filename = f"Agenda_{meeting.Meeting_Date.strftime('%Y-%m-%d')}.xlsx" if meeting else f"Agenda_{meeting_number}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )




class SuspiciousDateError(ValueError):
    """Exception raised when a meeting date is earlier than existing meetings."""
    pass


def _validate_meeting_form_data(form):
    """Parses and validates meeting form data."""
    meeting_number = form.get('meeting_number')
    meeting_type = form.get('meeting_type')
    
    # Check template validity using the model's mapping
    template_file = Meeting.TYPE_TO_TEMPLATE.get(meeting_type)
    if not template_file:
         raise ValueError(f"Invalid meeting type: {meeting_type}")
         
    template_path = os.path.join(current_app.static_folder, 'mtg_templates', template_file)
    
    if not os.path.exists(template_path):
         raise ValueError(f"Template file not found for meeting type: {meeting_type}")

    meeting_date_str = form.get('meeting_date')
    start_time_str = form.get('start_time')
    try:
        meeting_date = datetime.strptime(meeting_date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
    except (ValueError, TypeError):
         raise ValueError("Invalid date or time format.")

    # Validate that new meeting date is not earlier than the most recent meeting for this club
    club_id = get_current_club_id()
    query = Meeting.query
    if club_id:
        query = query.filter_by(club_id=club_id)
    most_recent_meeting = query.order_by(Meeting.Meeting_Date.desc()).first()
    
    ignore_suspicious_date = form.get('ignore_suspicious_date') == 'true'
    if not ignore_suspicious_date and most_recent_meeting and meeting_date < most_recent_meeting.Meeting_Date:
        raise SuspiciousDateError(f"Meeting date ({meeting_date.strftime('%Y-%m-%d')}) is earlier than the most recent meeting ({most_recent_meeting.Meeting_Date.strftime('%Y-%m-%d')}).")

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
    is_new = False
    
    if not meeting:
        is_new = True
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
            status='unpublished',
            club_id=get_current_club_id()
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

    if is_new:
        # Auto-add Staff to Roster
        from .models import UserClub, AuthRole
        club_id = get_current_club_id()
        if club_id:
            # Find all staff members for this club (Officers/Admins)
            staff_members = UserClub.query.join(AuthRole, UserClub.club_role_id == AuthRole.id)\
                .filter(UserClub.club_id == club_id, AuthRole.level > 1).all()
            
            # Add each staff member to the roster
            # Officers get order numbers starting from 1000
            # Filter to ensure we only count members who have a contact_id
            valid_staff = [m for m in staff_members if m.contact_id]
            
            # Pre-fetch Officer ticket
            from .models import Ticket
            officer_ticket = Ticket.query.filter_by(name='Officer').first()
            
            for i, membership in enumerate(valid_staff):
                roster_entry = Roster(
                    meeting_number=meeting.Meeting_Number,
                    contact_id=membership.contact_id,
                    order_number=1000 + i,
                    ticket=officer_ticket,
                    contact_type='Officer'
                )
                db.session.add(roster_entry)

    return meeting


def _generate_logs_from_template(meeting, template_file):
    """Reads the CSV template and generates session logs."""
    # Clear existing logs
    SessionLog.query.filter_by(Meeting_Number=meeting.Meeting_Number).delete()
    
    template_path = os.path.join(
        current_app.static_folder, 'mtg_templates', template_file)
        
    # Get current ExComm team from database for officer auto-population
    from .models import ExComm
    club_id = get_current_club_id()
    excomm = None
    excomm_officers = {}
    
    if club_id:
        # Get the most recent ExComm record for this club
        excomm = ExComm.query.filter_by(club_id=club_id).order_by(ExComm.id.desc()).first()
        
        if excomm:
            # Build officer mapping from ExComm model
            excomm_officers = excomm.get_officers()  # Returns dict like {'President': Contact, 'VPE': Contact, ...}

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
            if type_id == SessionTypeID.EVALUATION and meeting.ge_mode == 1:  # Individual Evaluation
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
            if not owner_id and excomm_officers:
                role_to_check = role_val
                if not role_to_check and session_type and session_type.role:
                        role_to_check = session_type.role.name
                
                if role_to_check:
                        # Check if this role exists in the ExComm officers dict
                        officer_contact = excomm_officers.get(role_to_check)
                        if officer_contact:
                            owner_id = officer_contact.id
                            credentials = derive_credentials(officer_contact)
            
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
@authorized_club_required
def create_from_template():
    # Check if user has permission to edit agenda
    if not is_authorized(Permissions.AGENDA_EDIT):
        return jsonify({'success': False, 'message': "You don't have permission to create meetings."}), 403
    
    try:
        # 1. Validation & Data Extraction
        data = _validate_meeting_form_data(request.form)
    except SuspiciousDateError as e:
        return jsonify({
            'success': False, 
            'suspicious_date': True, 
            'message': str(e)
        }), 400
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400

    try:
        # 2. Handle Media
        media_id = _get_or_create_media_id(data['media_url'])

        # 3. Create or Update Meeting
        meeting = _upsert_meeting_record(data, media_id)
        
        # Set club_id for the meeting
        from .club_context import get_current_club_id
        club_id = get_current_club_id()
        if club_id:
            meeting.club_id = club_id
        
        # Commit to ensure Meeting exists and has proper state before logs are created
        db.session.commit()

        # 4. Generate Session Logs from Template
        _generate_logs_from_template(meeting, data['template_file'])
        
        # Final Commit
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Meeting created successfully!',
            'redirect_url': url_for('agenda_bp.agenda', meeting_number=data['meeting_number'])
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating meeting: {e}")
        return jsonify({'success': False, 'message': f'Error processing template: {str(e)}'}), 500
        return redirect(url_for('agenda_bp.agenda'))



@agenda_bp.route('/agenda/update', methods=['POST'])
@login_required
@authorized_club_required
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
@authorized_club_required
def delete_log(log_id):
    log = db.session.get(SessionLog, log_id)
    if not log:
        return jsonify(success=False, message="Log not found"), 404

    # Security check: Ensure log belongs to current club via meeting
    club_id = get_current_club_id()
    if club_id and log.meeting and log.meeting.club_id != club_id:
        return jsonify(success=False, message="Unauthorized"), 403
    try:
        if log.Owner_ID:
            from .services.role_service import RoleService
            RoleService.cancel_meeting_role(log, log.Owner_ID, is_admin=True)

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
        if category:
            award_attr = f"best_{category.replace('-', '_')}_id"
            if hasattr(meeting, award_attr):
                setattr(meeting, award_attr, winner_id)

    # Calculate NPS (Average of non-blank scores)
    nps_avg = db.session.query(func.avg(Vote.score)).filter(
        Vote.meeting_number == meeting.Meeting_Number,
        Vote.score.isnot(None)
    ).scalar()

    if nps_avg is not None:
        meeting.nps = float(nps_avg)


@agenda_bp.route('/agenda/status/<int:meeting_number>', methods=['POST'])
@login_required
@authorized_club_required
def update_meeting_status(meeting_number):
    """Toggles the status of a meeting."""
    club_id = get_current_club_id()
    meeting = Meeting.query.filter_by(Meeting_Number=meeting_number)
    if club_id:
        meeting = meeting.filter(Meeting.club_id == club_id)
    meeting = meeting.first()

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
            # Full deletion flow using the model method
            success, error_msg = meeting.delete_full()
            
            if success:
                return jsonify(success=True, deleted=True)
            else:
                return jsonify(success=False, message=f"Deletion failed: {error_msg}"), 500
                
        except Exception as e:
             # Should be caught inside delete_full, but just in case
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
@authorized_club_required
def sync_tally(meeting_number):
    try:
        # Security check: Ensure meeting belongs to current club
        club_id = get_current_club_id()
        meeting = Meeting.query.filter_by(Meeting_Number=meeting_number)
        if club_id:
            meeting = meeting.filter(Meeting.club_id == club_id)
        if not meeting.first():
             return jsonify(success=False, message="Meeting not found"), 404

        context = MeetingExportContext(meeting_number)
        sync_participants_to_tally(context.participants_dict)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500
