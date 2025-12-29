# innoeduke/vpemaster/vpemaster-dev0.3/speech_logs_routes.py
from flask import Blueprint, jsonify, render_template, request, session, current_app
from . import db
from .models import SessionLog, Contact, Project, User, SessionType, Media, Role, Pathway, PathwayProject, LevelRole
from .auth.utils import login_required, is_authorized
from flask_login import current_user

from .utils import get_project_code
from sqlalchemy import distinct
from sqlalchemy.orm import joinedload
from datetime import datetime
import re

speech_logs_bp = Blueprint('speech_logs_bp', __name__)


@speech_logs_bp.route('/speech_logs')
@login_required
def show_speech_logs():
    # VPE/Admin can switch between 'member' and 'admin' view.
    # Default to 'member' view for everyone.
    can_view_all = is_authorized('SPEECH_LOGS_VIEW_ALL')
    view_mode = request.args.get('view_mode', 'member')
    
    # Even if they can view all, we default to member view unless they explicitly ask for admin
    if can_view_all and view_mode == 'admin':
        is_member_view = False
    else:
        is_member_view = True

    selected_meeting = request.args.get('meeting_number')
    selected_pathway = request.args.get('pathway')
    selected_level = request.args.get('level')
    selected_speaker = request.args.get('speaker_id')
    selected_status = request.args.get('status')
    selected_role = request.args.get('role')

    if is_member_view:
        if can_view_all and request.args.get('speaker_id'):
            # Admin impersonating a user in member view
            selected_speaker = request.args.get('speaker_id')
        else:
            user = current_user
            if user and user.Contact_ID:
                selected_speaker = user.Contact_ID
            else:
                selected_speaker = -1   # No logs for unlinked member

    impersonated_user_name = None
    if selected_speaker and selected_speaker != -1:
         try:
             c = Contact.query.get(int(selected_speaker))
             if c:
                 impersonated_user_name = c.Name
         except (ValueError, TypeError):
             pass

    all_pathways_from_db = Pathway.query.filter(Pathway.type != 'dummy', Pathway.status == 'active').order_by(Pathway.name).all()
    pathway_mapping = {p.name: p.abbr for p in all_pathways_from_db}

    grouped_pathways = {}
    for p in all_pathways_from_db:
        ptype = p.type or "Other"
        if ptype not in grouped_pathways:
            grouped_pathways[ptype] = []
        grouped_pathways[ptype].append(p.name)

    # Fetch available roles for the filter
    available_roles = Role.query.filter(
        Role.type.in_(['standard', 'club-specific'])
    ).order_by(Role.name).all()
    
    grouped_roles = {}
    for r in available_roles:
        # Capitalize type for display (e.g., "Standard", "Club-specific")
        rtype = r.type.replace('-', ' ').title() 
        if rtype not in grouped_roles:
            grouped_roles[rtype] = []
        grouped_roles[rtype].append(r.name)


    # Eager load all common relationships
    base_query = db.session.query(SessionLog).options(
        joinedload(SessionLog.media),
        joinedload(SessionLog.session_type).joinedload(SessionType.role),
        joinedload(SessionLog.meeting),
        joinedload(SessionLog.owner),
        joinedload(SessionLog.project)
    ).join(SessionType).join(Role, SessionType.role_id == Role.id).filter(
        Role.name.isnot(None),
        Role.name != '',
        Role.name != 'Backup Speaker',
        # 只允许standard或club-specific类型的role
        Role.type.in_(['standard', 'club-specific'])

    )

    if selected_speaker:
        base_query = base_query.filter(SessionLog.Owner_ID == selected_speaker)
    if selected_meeting:
        base_query = base_query.filter(
            SessionLog.Meeting_Number == selected_meeting)
    if selected_role:
        base_query = base_query.filter(Role.name == selected_role)

    all_logs = base_query.order_by(SessionLog.Meeting_Number.desc()).all()

    grouped_logs = {}
    processed_roles = set()

    for log in all_logs:
        display_level = "General"  # Default bucket for roles without a level
        log_type = 'role'
        if not log.session_type or not log.session_type.role:
            continue
        role_name = log.session_type.role.name

        is_prepared_speech = log.project and log.project.Format == 'Prepared Speech'

        if (log.session_type.Valid_for_Project and log.Project_ID and log.Project_ID != 60) or is_prepared_speech:
            log_type = 'speech'
            # Try to find the project in the user's current path first
            pp = None
            pathway_abbr = None
            
            if log.owner and log.owner.Current_Path:
                user_path = Pathway.query.filter_by(name=log.owner.Current_Path).first()
                if user_path:
                     pp = PathwayProject.query.filter_by(project_id=log.Project_ID, path_id=user_path.id).first()
                     if pp:
                         pathway_abbr = user_path.abbr

            # Fallback: specific series or other path if not found in user's current path
            if not pp and log.Project_ID:
                pp = PathwayProject.query.filter_by(project_id=log.Project_ID).first()
                if pp:
                    path_obj = Pathway.query.get(pp.path_id)
                    if path_obj:
                        pathway_abbr = path_obj.abbr

            if log.project:
                # Use the calculated pathway_abbr (which is from owner path or fallback)
                log.project_code = log.project.get_code(pathway_abbr)
            else:
                log.project_code = ""

            # Legacy code derivation (if needed, but pp logic covers it)
            # code = project_id_to_code(log.Project_ID, path_abbr) ...
        else:  # It's a role
            # Check if we've already processed this role for this person/meeting
            role_key = (log.Meeting_Number, log.Owner_ID, role_name)
            if role_key in processed_roles:
                continue  # Skip if already added
            processed_roles.add(role_key)  # Add to set

            # Now, get its level
            if log.current_path_level:
                match = re.match(r"[A-Z]+(\d+)", log.current_path_level)
                if match:
                    display_level = str(match.group(1))  # 确保类型一致性

        log.log_type = log_type

        if selected_level and display_level != selected_level:
            continue

        if selected_pathway and not log.Project_ID:
            continue

        if log_type == 'speech' and selected_pathway and \
           (not log.owner or log.owner.Current_Path != selected_pathway):
            continue


        if selected_status:
            if log_type == 'speech':
                if log.Status != selected_status:
                    continue  # Filter speeches by status
            else:
                # For roles, only show if they are linked to a project (e.g. Active Listening) AND match status
                if log.Project_ID and log.Status == selected_status:
                    pass # Keep it
                else:
                    continue  # Hide generic roles or non-matching status

        # --- Add to Group ---
        if display_level not in grouped_logs:
            grouped_logs[display_level] = []
        grouped_logs[display_level].append(log)

    def get_activity_sort_key(log):
        # Failsafe, should not be needed as we assign log_type in step 3
        if not hasattr(log, 'log_type'):
            return (99, -log.Meeting_Number)

        if log.log_type == 'speech':
            priority = 1  # 1. Speeches
        else:  # 'role'
            priority = 3  # 3. Roles

        # Sort by priority (1, 2, 3), then by descending meeting number
        return (priority, -log.Meeting_Number)

    # Sort logs within each group by meeting number
    for level in grouped_logs:
        grouped_logs[level].sort(key=get_activity_sort_key)

    # Sort the groups themselves (5, 4, 3, 2, 1, then General)
    def get_group_sort_key(level_key):
        try:
            val = int(level_key)
            return (0, -val)  # Sort numbers first, descending
        except (ValueError, TypeError):
            return (1, level_key)  # Sort non-numbers (e.g., "General") last

    sorted_grouped_logs = dict(
        sorted(grouped_logs.items(), key=lambda item: get_group_sort_key(item[0])))

    # Get speaker path info to identify elective projects correctly
    speaker_id = selected_speaker
    speaker_user = None
    if speaker_id and speaker_id != -1:
        try:
            speaker_contact = Contact.query.get(int(speaker_id))
            speaker_user = speaker_contact.user if speaker_contact else None
        except (ValueError, TypeError):
            pass
    elif is_member_view:
        speaker_user = current_user
    
    current_path_name = speaker_user.contact.Current_Path if speaker_user and speaker_user.contact else None
    pathway_obj = Pathway.query.filter_by(name=current_path_name).first() if current_path_name else None
    
    pp_mapping = {} # { project_id: type ('required', 'elective') }
    if pathway_obj:
        pathway_projects = PathwayProject.query.filter_by(path_id=pathway_obj.id).all()
        pp_mapping = {pp.project_id: pp.type for pp in pathway_projects}

    # Calculate completion summary
    level_requirements = LevelRole.query.order_by(LevelRole.level, LevelRole.type.desc()).all()
    completion_summary = {} # { level: { 'required': [], 'elective': [] } }

    used_log_ids = set() # Avoid double counting logs for the same requirement type

    for lr in level_requirements:
        level_str = str(lr.level)
        if level_str not in completion_summary:
            completion_summary[level_str] = {'required': [], 'elective': []}
        
        count = 0
        details = [] # List of satisfying items
        logs_for_level = grouped_logs.get(level_str, [])
        
        for log in logs_for_level:
            if log.id in used_log_ids:
                continue

            satisfied = False
            item_name = log.Session_Title or (log.project.Project_Name if log.project else None) or (log.session_type.Title if log.session_type else "Activity")
            
            if hasattr(log, 'project_code') and log.project_code:
                item_name = f"{log.project_code} {item_name}"

            # Normalize role names for comparison
            actual_role_name = (log.session_type.role.name if log.session_type and log.session_type.role else (log.session_type.Title if log.session_type else "")).strip().lower()
            target_role_name = lr.role.strip().lower()

            def normalize(s):
                if not s: return ""
                return s.strip().replace(' ', '').replace('-', '').lower()

            norm_actual = normalize(actual_role_name)
            norm_target = normalize(target_role_name)

            # 1. Match by literal role name or common variations
            is_role_match = (norm_actual == norm_target)
            
            # Handle specific aliases
            if not is_role_match:
                aliases = {
                    'topicmaster': 'topicsmaster',
                    'topicsmaster': 'topicmaster',
                    'tme': 'toastmaster',
                    'toastmaster': 'tme',
                    'ge': 'generalevaluator',
                    'generalevaluator': 'ge'
                }
                if aliases.get(norm_actual) == norm_target:
                    is_role_match = True

            if is_role_match:
                satisfied = True
            
            # 2. Match by category (if lr.role is a general category)
            elif lr.role.lower() == 'speech' and log.log_type == 'speech':
                if pp_mapping.get(log.Project_ID) == 'required' or not pp_mapping:
                    satisfied = True
            elif lr.role.lower() == 'elective project' and log.log_type == 'speech':
                if pp_mapping.get(log.Project_ID) == 'elective':
                    satisfied = True
            
            # 3. Special case for "Individual Evaluator" logged as a project or role
            elif target_role_name == 'individual evaluator' and 'evaluat' in actual_role_name:
                satisfied = True
            
            if satisfied:
                if log.Status == 'Completed' or log.log_type == 'role':
                    count += 1
                    details.append({'name': item_name, 'status': 'completed'})
                    used_log_ids.add(log.id)
                    if count >= lr.count_required:
                        break # Satisfied this requirement
        
        # Add placeholders for pending items
        pending_count = max(0, lr.count_required - count)
        for i in range(pending_count):
            details.append({'name': f"Pending {lr.role}", 'status': 'pending'})

        target_group = 'elective' if lr.type == 'elective' else 'required'
        completion_summary[level_str][target_group].append({
            'role': lr.role,
            'count': count,
            'required': lr.count_required,
            'requirement_items': details
        })

    meeting_numbers = sorted([m[0] for m in db.session.query(
        distinct(SessionLog.Meeting_Number)).join(Project).all()], reverse=True)
    speakers = db.session.query(Contact).join(
        SessionLog, Contact.id == SessionLog.Owner_ID).distinct().order_by(Contact.Name).all()
    
    # Fetch all contacts for the impersonation dropdown
    all_contacts = Contact.query.order_by(Contact.Name).all()

    # Convert project objects to a list of dictionaries
    projects = Project.query.order_by(Project.Project_Name).all()

    all_pp = db.session.query(PathwayProject, Pathway.abbr).join(Pathway).all()
    project_codes_lookup = {}  # {project_id: {path_abbr: {'code': code, 'level': level}, ...}}
    for pp, path_abbr in all_pp:
        if pp.project_id not in project_codes_lookup:
            project_codes_lookup[pp.project_id] = {}
        project_codes_lookup[pp.project_id][path_abbr] = {'code': pp.code, 'level': pp.level}

    projects_data = [
        {
            "id": p.id,
            "Project_Name": p.Project_Name,
            "path_codes": project_codes_lookup.get(p.id, {}),
            "Duration_Min": p.Duration_Min,
            "Duration_Max": p.Duration_Max
        }
        for p in projects
    ]



    # Fetch series initials from Pathway table (where abbr is not null/empty)
    pathways_db = Pathway.query.filter_by(status='active').order_by(Pathway.name).all()
    SERIES_INITIALS = {p.name: p.abbr for p in pathways_db if p.abbr}
    today_date = datetime.today().date()

    all_roles_db = Role.query.all()
    role_icons = {
        r.name: r.icon or current_app.config['DEFAULT_ROLE_ICON']
        for r in all_roles_db
    }

    # Construct a legacy-style roles_config for the template if needed
    roles_config = {
        r.name.upper().replace(' ', '_').replace('-', '_'): {
            'name': r.name,
            'icon': r.icon,
            'award': r.award_category,
            'unique': r.is_distinct
        } for r in all_roles_db
    }

    return render_template(
        'speech_logs.html',
        grouped_logs=sorted_grouped_logs,
        roles_config=roles_config,
        roles=grouped_roles,
        role_icons=role_icons,
        meeting_numbers=meeting_numbers,
        speakers=speakers,
        pathways=grouped_pathways,
        levels=range(1, 6),
        projects=projects_data,  # This is used for allProjects in JS
        series_initials=SERIES_INITIALS,  # Pass initials map for template
        today_date=today_date,
        level_roles=LevelRole.query.order_by(LevelRole.level, LevelRole.type).all(),
        completion_summary=completion_summary,
        selected_filters={
            'meeting_number': selected_meeting,
            'pathway': selected_pathway,
            'level': selected_level,
            'speaker_id': selected_speaker,
            'status': selected_status,
            'role': selected_role
        },
        is_member_view=is_member_view,
        can_view_all=can_view_all,
        view_mode=view_mode,
        pathway_mapping=pathway_mapping,
        all_contacts=all_contacts,
        impersonated_user_name=impersonated_user_name
    )


@speech_logs_bp.route('/speech_log/details/<int:log_id>', methods=['GET'])
@login_required
def get_speech_log_details(log_id):
    """
    Fetches details for a specific speech log to populate the edit modal.
    """
    log = db.session.query(SessionLog).options(
        joinedload(SessionLog.media)).get_or_404(log_id)

    current_user_contact_id = current_user.Contact_ID if current_user.is_authenticated else None

    if not is_authorized('SPEECH_LOGS_EDIT_ALL'):
        if log.Owner_ID != current_user_contact_id:
            return jsonify(success=False, message="Permission denied. You can only view details for your own speech logs."), 403


    # Use the helper function to get project code
    project_code = ""
    pathway_name_to_return = log.owner.Current_Path if log.owner and log.owner.Current_Path else "Presentation Mastery"
    
    # Better logic: if there is a Project linked, try to find the pathway it belongs to
    # especially for Presentations or if the user is not linked to a path
    level = 1
    if log.Project_ID and log.project:
        pp, path_obj = log.project.resolve_context(log.owner.Current_Path if log.owner else None)
        
        if path_obj:
            pathway_name_to_return = path_obj.name
        
        if pp:
             if path_obj and path_obj.abbr:
                 log.project_code = f"{path_obj.abbr}{pp.code}"
             else:
                 log.project_code = pp.code
             
             if pp.level:
                level = pp.level
        else:
             log.project_code = ""
             if log.Project_ID == 60: # Generic
                 log.project_code = "TM1.0"

    log_data = {
        "id": log.id,
        "Session_Title": log.Session_Title,
        "Project_ID": log.Project_ID,
        "pathway": pathway_name_to_return,
        "level": level,
        "Media_URL": log.media.url if log.media else ""
    }

    return jsonify(success=True, log=log_data)


@speech_logs_bp.route('/speech_log/update/<int:log_id>', methods=['POST'])
@login_required
def update_speech_log(log_id):
    """
    Updates a speech log with new data from the edit modal.
    """
    log = db.session.query(SessionLog).options(
        joinedload(SessionLog.owner),
        joinedload(SessionLog.session_type),
        joinedload(SessionLog.project)
    ).get_or_404(log_id)

    current_user_contact_id = current_user.Contact_ID if current_user.is_authenticated else None

    if not is_authorized('SPEECH_LOGS_EDIT_ALL'):
        is_owner = (current_user_contact_id == log.Owner_ID)
        if not (is_authorized('SPEECH_LOGS_VIEW_OWN') and is_owner):
            return jsonify(success=False, message="Permission denied. You can only edit your own speech logs."), 403


    data = request.get_json()

    session_type_title = data.get('session_type_title')
    media_url = data.get('media_url') or None

    # Pre-fetch records to avoid autoflush-related deadlocks.
    project_id = data.get('project_id')
    updated_project = None

    if project_id and project_id not in [None, "", "null"]:
        updated_project = Project.query.get(project_id)


    if 'session_title' in data:
        log.Session_Title = data['session_title']

    if media_url:
        # If URL is provided, update or create media record
        if log.media:
            log.media.url = media_url
        else:
            log.media = Media(url=media_url)
    elif log.media:
        # If URL is blank but a media record exists, delete it
        db.session.delete(log.media)

    # If it's a presentation and the title is *still* blank, then default to the presentation's name
    if updated_project and not log.Session_Title:
        log.Session_Title = updated_project.Project_Name

    if 'pathway' in data and log.owner and log.owner.user:
        # Only update user's current path if it's a standard pathway, not a series
        # We can heuristic check if "Series" is in the name, or check DB. 
        # For now, simplistic approach: if it has "Series" in name, assume it's presentation series and don't change user's main path.
        if "Series" not in data['pathway']:
             user = log.owner.user
             user.Current_Path = data['pathway']
             db.session.add(user)

    # --- Duration Update Logic Start ---
    # Goal: Update duration only if structurally changed (Project or SessionType), otherwise preserve manual edits.
    
    # 1. Identify Changes
    project_changed = False
    session_type_changed = False
    
    # Check Project Change
    new_project_id = data.get('project_id')
    if new_project_id in [None, "", "null"]:
        new_project_id = None
    else:
        try:
            new_project_id = int(new_project_id)
        except (ValueError, TypeError):
             new_project_id = None

    if log.Project_ID != new_project_id:
        project_changed = True
    
    # Check Session Type Change
    if session_type_title and log.session_type.Title != session_type_title:
        session_type_changed = True

    # 2. Update Basic Fields (Project ID)
    if 'project_id' in data: # check if key exists in payload
         log.Project_ID = new_project_id

    # 3. Apply Duration Updates based on Priority
    # Priority 1: Project Changed (and we have a project)
    if project_changed and log.Project_ID:
        if updated_project: 
             log.Duration_Min = updated_project.Duration_Min
             log.Duration_Max = updated_project.Duration_Max
    
    # Priority 2: Session Type Changed (and Project didn't handle it)
    elif session_type_changed:
        # Fetch the NEW session type to get defaults
        new_st = SessionType.query.filter_by(Title=session_type_title).first()
        if new_st:
            log.Duration_Min = new_st.Duration_Min
            log.Duration_Max = new_st.Duration_Max
    
    # Priority 3: No Structural Change -> Do NOT update duration (Preserve manual edits)

    # --- Duration Update Logic End ---

    try:
        db.session.commit()
        project_name = "N/A"
        project_code = None
        pathway = log.owner.Current_Path if log.owner else "N/A"

        if log.Project_ID:
            project = Project.query.get(log.Project_ID)
            if project:
                project_name = project.Project_Name
                # Find series info
                pp = PathwayProject.query.filter_by(project_id=project.id).first()
                if pp:
                    pathway_obj = Pathway.query.get(pp.path_id)
                    if pathway_obj:
                        pathway = pathway_obj.name
                        project_code = f"{pathway_obj.abbr}{pp.code}"

        return jsonify(success=True,
                       session_title=log.Session_Title,
                       project_name=project_name,
                       project_code=project_code,
                       pathway=pathway,
                       project_id=log.Project_ID,
                       duration_min=log.Duration_Min,
                       duration_max=log.Duration_Max,
                       media_url=media_url)

    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@speech_logs_bp.route('/speech_log/suspend/<int:log_id>', methods=['POST'])
@login_required
def suspend_speech_log(log_id):
    if not is_authorized('SPEECH_LOGS_EDIT_ALL'):
        return jsonify(success=False, message="Permission denied"), 403

    log = SessionLog.query.get_or_404(log_id)
    log.Status = 'Delivered'
    try:
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500




@speech_logs_bp.route('/speech_log/complete/<int:log_id>', methods=['POST'])
@login_required
def complete_speech_log(log_id):
    log = SessionLog.query.get_or_404(log_id)

    current_user_contact_id = current_user.Contact_ID if current_user.is_authenticated else None

    if not is_authorized('SPEECH_LOGS_EDIT_ALL'):
        if log.Owner_ID != current_user_contact_id:
            return jsonify(success=False, message="Permission denied."), 403
        # Also check if meeting is in the past for non-admins
        if log.meeting and log.meeting.Meeting_Date and log.meeting.Meeting_Date >= datetime.today().date():
            return jsonify(success=False, message="You can only complete logs for past meetings."), 403


    log.Status = 'Completed'

    try:
        db.session.commit()
        
        # Trigger metadata sync (including Next_Project calculation) after commit
        if log.Owner_ID:
            from .utils import sync_contact_metadata
            sync_contact_metadata(log.Owner_ID)
            
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500
