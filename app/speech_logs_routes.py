# innoeduke/vpemaster/vpemaster-dev0.3/speech_logs_routes.py
from flask import Blueprint, jsonify, render_template, request, session, current_app
from . import db
from .models import SessionLog, Contact, Project, User, SessionType, Media, MeetingRole, Pathway, PathwayProject, LevelRole, Achievement, Meeting
from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
from flask_login import current_user
from .utils import (
    get_project_code, 
    build_pathway_project_cache, 
    normalize_role_name, 
    get_role_aliases,
    get_dropdown_metadata
)
from sqlalchemy import distinct
from sqlalchemy.orm import joinedload
from datetime import datetime
import re
from .constants import ProjectID

speech_logs_bp = Blueprint('speech_logs_bp', __name__)


# ============================================================================
# PRIVATE HELPER FUNCTIONS
# ============================================================================

def _get_view_settings():
    """
    Determine view permissions and mode.
    Returns: (can_view_all, view_mode, is_member_view)
    """
    can_view_all = is_authorized(Permissions.SPEECH_LOGS_VIEW_ALL)
    view_mode = request.args.get('view_mode', 'member')
    
    if can_view_all and view_mode == 'admin':
        is_member_view = False
    else:
        is_member_view = True
    
    return can_view_all, view_mode, is_member_view


def _parse_filters(is_member_view, can_view_all):
    """
    Parse request arguments into filter dictionary.
    Returns: dict with filter values
    """
    filters = {
        'meeting_number': request.args.get('meeting_number'),
        'pathway': request.args.get('pathway'),
        'level': request.args.get('level'),
        'speaker_id': request.args.get('speaker_id'),
        'status': request.args.get('status'),
        'role': request.args.get('role')
    }
    
    # Handle speaker_id for member view
    if is_member_view:
        if can_view_all and filters['speaker_id']:
            # Admin impersonating user
            pass
        else:
            if current_user and current_user.Contact_ID:
                filters['speaker_id'] = current_user.Contact_ID
            else:
                filters['speaker_id'] = -1
    
    return filters


def _get_viewed_contact(speaker_id):
    """
    Get contact object for the speaker being viewed.
    Returns: Contact object or None
    """
    if not speaker_id or speaker_id == -1:
        return None
    
    try:
        return db.session.get(Contact, int(speaker_id))
    except (ValueError, TypeError):
        return None


def _get_pathway_info(viewed_contact, raw_pathway, filters):
    """
    Determine pathway selection and get member pathways.
    Returns: dict with pathway info
    """
    selected_pathway = filters.get('pathway')
    
    # Handle 'all' selection
    if raw_pathway == 'all':
        selected_pathway = 'all'
    elif not raw_pathway and viewed_contact and viewed_contact.Current_Path:
        selected_pathway = viewed_contact.Current_Path
    
    # Get member pathways using model method
    member_pathways = []
    if viewed_contact:
        member_pathways = viewed_contact.get_member_pathways()
        
        # Ensure selected pathway is in list
        if selected_pathway and selected_pathway != 'all' and selected_pathway not in member_pathways:
            member_pathways.append(selected_pathway)
            member_pathways.sort()
    
    return {
        'selected_pathway': selected_pathway,
        'member_pathways': member_pathways,
        'impersonated_user_name': viewed_contact.Name if viewed_contact else None
    }


def _fetch_logs_with_filters(filters):
    """
    Build and execute query for session logs with filters.
    Returns: list of SessionLog objects
    """
    base_query = db.session.query(SessionLog).options(
        joinedload(SessionLog.media),
        joinedload(SessionLog.session_type).joinedload(SessionType.role),
        joinedload(SessionLog.meeting),
        joinedload(SessionLog.owner),
        joinedload(SessionLog.project)
    ).join(SessionType).join(MeetingRole, SessionType.role_id == MeetingRole.id).filter(
        MeetingRole.name.isnot(None),
        MeetingRole.name != '',
        MeetingRole.type.in_(['standard', 'club-specific'])
    )
    
    if filters['speaker_id']:
        base_query = base_query.filter(SessionLog.Owner_ID == filters['speaker_id'])
    if filters['meeting_number']:
        base_query = base_query.filter(SessionLog.Meeting_Number == filters['meeting_number'])
    if filters['role']:
        base_query = base_query.filter(MeetingRole.name == filters['role'])
    
    return base_query.order_by(SessionLog.Meeting_Number.desc()).all()


def _process_logs(all_logs, filters, pathway_cache):
    """
    Process logs: determine type/level, apply filters, group by level.
    Returns: dict of grouped logs {level: [logs]}
    """
    grouped_logs = {}
    processed_roles = set()
    
    for log in all_logs:
        # Use model method to get display level and type
        display_level, log_type, project_code = log.get_display_level_and_type(pathway_cache)
        
        # Store for filtering
        log.display_level = display_level
        log.log_type = log_type
        log.project_code = project_code
        log.display_pathway = log.pathway
        
        # Identify Presentation Series
        # Updated to check project property instead of session type title
        if log.project and log.project.is_presentation:
             if pathway_cache and log.Project_ID in pathway_cache:
                  pp_data = pathway_cache[log.Project_ID]
                  for path_id, pp in pp_data.items():
                       # Check if pathway is of type 'presentation' (from regex check) or contains Series in name
                       p_type = (pp.pathway.type or '').lower()
                       if 'presentation' in p_type or 'series' in pp.pathway.name.lower():
                           log.presentation_series = pp.pathway.name
                           log.presentation_code = pp.code
                           # Also set display level and type specifically for presentation if needed
                           log.log_type = 'presentation' # To trigger specific card styling if template uses it
                           break
        
        # Deduplicate roles
        if log_type == 'role' and not log.Project_ID:
            role_key = (log.Meeting_Number, log.Owner_ID, log.session_type.role.name)
            if role_key in processed_roles:
                continue
            processed_roles.add(role_key)
        
        # Apply filters using model method
        if not log.matches_filters(
            pathway=filters['pathway'],
            level=filters['level'],
            status=filters['status'],
            log_type=log_type
        ):
            continue
        
        # Special check for speeches without project
        if filters['pathway'] and log_type == 'speech' and not log.Project_ID:
            continue
        
        # Add to group
        if display_level not in grouped_logs:
            grouped_logs[display_level] = []
        grouped_logs[display_level].append(log)
    
    return grouped_logs


def _sort_and_consolidate(grouped_logs):
    """
    Sort logs within groups and consolidate role entries.
    Returns: sorted grouped logs dict
    """
    def get_activity_sort_key(log):
        if not hasattr(log, 'log_type'):
            return (99, -log.Meeting_Number)
        priority = 1 if log.log_type == 'speech' else 3
        return (priority, -log.Meeting_Number)
    
    def get_group_sort_key(level_key):
        try:
            return (0, -int(level_key))
        except (ValueError, TypeError):
            return (1, level_key)
    
    for level in grouped_logs:
        grouped_logs[level].sort(key=get_activity_sort_key)
        
        # Consolidate role logs
        consolidated_group = []
        role_group_map = {}
        
        for item in grouped_logs[level]:
            if item.log_type == 'role' and not item.Project_ID:
                role_name = item.session_type.role.name if item.session_type and item.session_type.role else item.session_type.Title
                owner_id = item.Owner_ID
                key = (owner_id, role_name)
                
                if key in role_group_map:
                    role_group_map[key]['logs'].append(item)
                else:
                    new_group = {
                        'log_type': 'grouped_role',
                        'role_name': role_name,
                        'session_type': item.session_type,
                        'owner': item.owner,
                        'project_code': item.project_code,
                        'display_pathway': item.display_pathway,
                        'logs': [item]
                    }
                    role_group_map[key] = new_group
                    consolidated_group.append(new_group)
            else:
                consolidated_group.append(item)
        
        # Unwrap single-item groups
        final_list = []
        for item in consolidated_group:
            if isinstance(item, dict) and item.get('log_type') == 'grouped_role' and len(item['logs']) == 1:
                final_list.append(item['logs'][0])
            else:
                final_list.append(item)
        
        grouped_logs[level] = final_list
    
    # Sort groups
    sorted_grouped_logs = dict(
        sorted(grouped_logs.items(), key=lambda item: get_group_sort_key(item[0]))
    )
    
    return sorted_grouped_logs


def _calculate_completion_summary(grouped_logs, pp_mapping):
    """
    Calculate completion summary against LevelRole requirements.
    Uses normalize_role_name and get_role_aliases from utils.
    """
    level_requirements = LevelRole.query.order_by(LevelRole.level, LevelRole.type.desc()).all()
    completion_summary = {}
    used_log_ids = set()
    role_aliases = get_role_aliases()
    
    for lr in level_requirements:
        level_str = str(lr.level)
        if level_str not in completion_summary:
            completion_summary[level_str] = {'required': [], 'elective': []}
        
        count = 0
        details = []
        logs_for_level = grouped_logs.get(level_str, [])
        
        for entry in logs_for_level:
            items_to_process = entry['logs'] if isinstance(entry, dict) and entry.get('log_type') == 'grouped_role' else [entry]
            
            for log in items_to_process:
                if log.id in used_log_ids:
                    continue
                
                satisfied = False
                item_name = log.Session_Title or (log.project.Project_Name if log.project else None) or (log.session_type.Title if log.session_type else "Activity")
                
                if hasattr(log, 'project_code') and log.project_code:
                    item_name = f"{log.project_code} {item_name}"
                
                actual_role_name = (log.session_type.role.name if log.session_type and log.session_type.role else (log.session_type.Title if log.session_type else "")).strip().lower()
                target_role_name = lr.role.strip().lower()
                
                norm_actual = normalize_role_name(actual_role_name)
                norm_target = normalize_role_name(target_role_name)
                
                is_role_match = (norm_actual == norm_target)
                if not is_role_match and role_aliases.get(norm_actual) == norm_target:
                    is_role_match = True
                
                if is_role_match:
                    satisfied = True
                elif lr.role.lower() == 'speech' and hasattr(log, 'log_type') and (log.log_type == 'speech' or log.log_type == 'presentation'):
                    # Presentations always count as speeches regardless of pathway mapping
                    if log.log_type == 'presentation' or pp_mapping.get(log.Project_ID) == 'required' or not pp_mapping:
                        satisfied = True
                # Check for specific presentation series requirement (e.g. "Successful Club Series")
                elif hasattr(log, 'presentation_series') and log.presentation_series:
                    if normalize_role_name(log.presentation_series.lower()) == norm_target:
                        satisfied = True
                elif lr.role.lower() == 'elective project' and hasattr(log, 'log_type') and log.log_type == 'speech':
                    if pp_mapping.get(log.Project_ID) == 'elective':
                        satisfied = True
                elif target_role_name == 'individual evaluator' and 'evaluat' in actual_role_name:
                    satisfied = True
               
                if satisfied:
                    if log.Status == 'Completed' or (hasattr(log, 'log_type') and log.log_type == 'role'):
                        count += 1
                        details.append({'name': item_name, 'status': 'completed'})
                        used_log_ids.add(log.id)
                        if count >= lr.count_required:
                            break
        
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
    
    return completion_summary


def _get_speaker_user(viewed_contact, is_member_view):
    """Get the User object for the speaker."""
    if viewed_contact:
        return viewed_contact.user
    elif is_member_view:
        return current_user
    return None


def _get_pathway_project_mapping(speaker_user):
    """Get mapping of project IDs to types (required/elective)."""
    if not speaker_user or not speaker_user.contact or not speaker_user.contact.Current_Path:
        return {}
    
    pathway_obj = Pathway.query.filter_by(name=speaker_user.contact.Current_Path).first()
    if not pathway_obj:
        return {}
    
    pathway_projects = PathwayProject.query.filter_by(path_id=pathway_obj.id).all()
    return {pp.project_id: pp.type for pp in pathway_projects}


def _get_achievement_status(speaker_id, speaker_user, selected_pathway):
    """
    Get completed levels and determine active level.
    Uses Contact.get_completed_levels() model method.
    """
    completed_levels = set()
    target_path_name = selected_pathway
    
    if not target_path_name and speaker_user and speaker_user.contact and speaker_user.contact.Current_Path:
        target_path_name = speaker_user.contact.Current_Path
    
    if speaker_id and speaker_id != -1 and target_path_name:
        try:
            contact = db.session.get(Contact, int(speaker_id))
            if contact:
                completed_levels = contact.get_completed_levels(target_path_name)
        except (ValueError, TypeError):
            pass
    
    # Determine active level
    active_level = 1
    for l in range(1, 6):
        if l not in completed_levels:
            active_level = l
            break
    
    if all(i in completed_levels for i in range(1, 6)):
        active_level = 5
    
    return completed_levels, active_level


def _get_role_metadata():
    """Fetch role icons for template."""
    all_roles_db = MeetingRole.query.all()
    role_icons = {
        r.name: r.icon or current_app.config['DEFAULT_ROLE_ICON']
        for r in all_roles_db
    }
    
    return role_icons


def _get_level_progress_html(user_id, level, pathway_id=None):
    """
    Generate the HTML for the level progress summary.
    """
    # Create minimal filter set for this user
    filters = {
        'meeting_number': None,
        'pathway': pathway_id, # This might need to be the name or ID depending on usage
        'level': None,
        'speaker_id': user_id,
        'status': None,
        'role': None
    }
    
    # Needs to be able to get the contact for the user_id
    contact = db.session.get(Contact, user_id)
    if not contact:
        return ""

    if not filters['pathway'] and contact.Current_Path:
        filters['pathway'] = contact.Current_Path
        
    # We need to fetch logs again to calculate progress
    # This might be expensive but necessary for accurate update
    all_logs = _fetch_logs_with_filters(filters)
    
    project_ids = [log.Project_ID for log in all_logs if log.Project_ID]
    pathway_cache = build_pathway_project_cache(project_ids=project_ids)
    
    grouped_logs = _process_logs(all_logs, filters, pathway_cache)
    sorted_grouped_logs = _sort_and_consolidate(grouped_logs)
    
    speaker_user = contact.user
    pp_mapping = _get_pathway_project_mapping(speaker_user)
    
    completion_summary = _calculate_completion_summary(grouped_logs, pp_mapping)
    
    summary = completion_summary.get(str(level))
    
    return render_template('partials/_level_progress.html', summary=summary)


def _get_terms():
    """
    Generate a list of half-year terms (e.g. '2025 Jan-Jun', '2025 Jul-Dec').
    Returns a list of dicts: {'label': str, 'start': str(YYYY-MM-DD), 'end': str(YYYY-MM-DD), 'id': str}
    Goes back 5 years and forward 1 year from today.
    """
    today = datetime.today()
    current_year = today.year
    terms = []
    
    # Generate terms from 5 years ago to next year
    for year in range(current_year - 5, current_year + 2):
        # Jan-Jun
        terms.append({
            'label': f"{year} Jan-Jun",
            'id': f"{year}_1",
            'start': f"{year}-01-01",
            'end': f"{year}-06-30"
        })
        # Jul-Dec
        terms.append({
            'label': f"{year} Jul-Dec",
            'id': f"{year}_2",
            'start': f"{year}-07-01",
            'end': f"{year}-12-31"
        })
    
    # Sort descending
    terms.sort(key=lambda x: x['start'], reverse=True)
    return terms


def _get_active_term(terms):
    """
    Find the term corresponding to today's date.
    """
    today_str = datetime.today().strftime('%Y-%m-%d')
    for term in terms:
        if term['start'] <= today_str <= term['end']:
            return term
    return terms[0] if terms else None



# ============================================================================
# MAIN ROUTE
# ============================================================================

@speech_logs_bp.route('/speech_logs')
@login_required
def show_speech_logs():
    """
    Display speech logs with filtering and progress tracking.
    Refactored for performance and maintainability.
    """
    # 1. Get view settings and filters
    can_view_all, view_mode, is_member_view = _get_view_settings()
    filters = _parse_filters(is_member_view, can_view_all)
    
    # 2. Get viewed contact
    viewed_contact = _get_viewed_contact(filters['speaker_id'])
    
    # 3. Get pathway information
    pathway_info = _get_pathway_info(viewed_contact, request.args.get('pathway'), filters)
    filters['pathway'] = pathway_info['selected_pathway']
    
    # 4. Get dropdown metadata (using utils)
    dropdown_data = get_dropdown_metadata()
    
    # 5. Fetch logs
    all_logs = _fetch_logs_with_filters(filters)
    
    # 6. Build pathway cache for performance
    project_ids = [log.Project_ID for log in all_logs if log.Project_ID]
    pathway_cache = build_pathway_project_cache(project_ids=project_ids)
    
    # 7. Process logs
    grouped_logs = _process_logs(all_logs, filters, pathway_cache)
    sorted_grouped_logs = _sort_and_consolidate(grouped_logs)
    
    # 8. Calculate completion summary
    speaker_user = _get_speaker_user(viewed_contact, is_member_view)
    pp_mapping = _get_pathway_project_mapping(speaker_user)
    completion_summary = _calculate_completion_summary(grouped_logs, pp_mapping)
    
    # 9. Get achievement status
    completed_levels, active_level = _get_achievement_status(
        filters['speaker_id'], speaker_user, filters['pathway']
    )
    
    # 10. Get role metadata
    role_icons = _get_role_metadata()
    
    # 11. Render template
    return render_template(
        'speech_logs.html',
        grouped_logs=sorted_grouped_logs,
        roles=dropdown_data['roles'],
        role_icons=role_icons,
        pathways=dropdown_data['pathways'],
        levels=range(1, 6),
        completed_levels=completed_levels,
        projects=dropdown_data['projects'],
        today_date=datetime.today().date(),
        completion_summary=completion_summary,
        selected_filters=filters,
        is_member_view=is_member_view,
        can_view_all=can_view_all,
        view_mode=view_mode,
        pathway_mapping=dropdown_data['pathway_mapping'],
        all_contacts=dropdown_data['all_contacts'],
        viewed_contact=viewed_contact,
        member_pathways=pathway_info['member_pathways'],
        active_level=active_level,
        ProjectID=ProjectID
    )


@speech_logs_bp.route('/speech_logs/projects')
@login_required
def show_project_view():
    """
    Display speech logs in a project-centric view (bar chart style).
    Accessible to admins mainly, but logic could allow others.
    """
    if not is_authorized(Permissions.SPEECH_LOGS_VIEW_ALL):
        # Or redirect to member view if not admin? 
        # For now, let's assume this is an admin-specific view or general view but showing all projects.
        # If regular user accesses, maybe show only their stats? 
        # The requirement implies Admin View replacement, so let's check admin permission.
        pass # Allow access, but maybe filter content if needed? 
             # Implementation plan says "Admin View" features.
             
    terms = _get_terms()
    # Get dropdown data for filter
    # Get dropdown data for filter
    # User requested: show pathways.path (name) with pathway.type=pathway, separated by status
    pathways_query = db.session.query(Pathway.name, Pathway.status).filter(Pathway.type == 'pathway').order_by(Pathway.name).all()
    
    active_pathways = []
    inactive_pathways = []
    
    for name, status in pathways_query:
        if status == 'active':
            active_pathways.append(name)
        else:
            inactive_pathways.append(name)
    
    selected_term_id = request.args.get('term')
    selected_pathway_id = request.args.get('pathway')
    
    current_term = None
    if selected_term_id:
        current_term = next((t for t in terms if t['id'] == selected_term_id), None)
    
    if not current_term:
        current_term = _get_active_term(terms)
        
    # Query Data
    # We want count of sessions per project within the date range
    start_date = current_term['start']
    end_date = current_term['end']
    
    filters = [
        SessionLog.Project_ID.isnot(None),
        SessionLog.Project_ID != ProjectID.GENERIC,
        SessionLog.meeting.has(Meeting.Meeting_Date.between(start_date, end_date))
    ]
    
    if selected_pathway_id:
        filters.append(SessionLog.pathway == selected_pathway_id)
        
    query = db.session.query(SessionLog).join(SessionLog.meeting).filter(*filters).order_by(SessionLog.Meeting_Number.asc()).options(
        joinedload(SessionLog.project),
        joinedload(SessionLog.owner)
    )
    
    logs = query.all()
    
    # Process into Chart Data
    # Structure: { project_id: { 'project': ProjectObj, 'count': int, 'owners': [ContactObj] } }
    project_data_map = {}
    
    for log in logs:
        if not log.project:
            continue
            
        pid = log.Project_ID
        if pid not in project_data_map:
            project_data_map[pid] = {
                'project_name': log.project.Project_Name,
                'count': 0,
                'status_counts': {'Completed': 0, 'Delivered': 0, 'Booked': 0},
                'owners': []
            }
        
        project_data_map[pid]['count'] += 1
        
        status = log.Status if log.Status in ['Completed', 'Delivered', 'Booked'] else 'Booked' # Default to Booked or maybe 'Other'?
        if status not in project_data_map[pid]['status_counts']:
             project_data_map[pid]['status_counts'][status] = 0
        project_data_map[pid]['status_counts'][status] += 1
        
        if log.owner:
            project_data_map[pid]['owners'].append(log.owner)
            
    # Convert to list and sort by count desc
    chart_data = sorted(
        project_data_map.values(), 
        key=lambda x: x['count'], 
        reverse=True
    )
    
    return render_template(
        'project_view.html',
        terms=terms,
        current_term=current_term,
        chart_data=chart_data,
        active_pathways=active_pathways,
        inactive_pathways=inactive_pathways,
        selected_pathway=selected_pathway_id
    )


# ============================================================================
# OTHER ROUTES (unchanged)
# ============================================================================

@speech_logs_bp.route('/speech_log/details/<int:log_id>', methods=['GET'])
@login_required
def get_speech_log_details(log_id):
    """
    Fetches details for a specific speech log to populate the edit modal.
    """
    log = db.session.query(SessionLog).options(
        joinedload(SessionLog.media)).get_or_404(log_id)

    current_user_contact_id = current_user.Contact_ID if current_user.is_authenticated else None

    if not is_authorized(Permissions.SPEECH_LOGS_EDIT_ALL):
        if log.Owner_ID != current_user_contact_id:
            return jsonify(success=False, message="Permission denied. You can only view details for your own speech logs."), 403


    # Use the helper function to get project code
    project_code = ""
    pathway_name_to_return = log.owner.Current_Path if log.owner and log.owner.Current_Path else "Presentation Mastery"
    level = 1
    
    # Better logic: if there is a Project linked, try to find the pathway it belongs to
    # especially for Presentations or if the user is not linked to a path
    if log.Project_ID and log.project:
        # 1. First, establish the pathway context
        if log.project_code:
            match = re.match(r"([A-Z]+)", log.project_code)
            if match:
                abbr = match.group(1)
                pathway_db = Pathway.query.filter_by(abbr=abbr).first()
                if pathway_db:
                    pathway_name_to_return = pathway_db.name

        if not pathway_name_to_return and log.owner:
            pathway_name_to_return = log.owner.Current_Path

        # 2. Derive level and project code based on that pathway
        level = log.project.get_level(pathway_name_to_return)
        
        if not getattr(log, 'project_code', None):
            log.project_code = log.project.get_code(pathway_name_to_return)

    log_data = {
        "id": log.id,
        "Session_Title": log.Session_Title,
        "Project_ID": log.Project_ID,
        "pathway": pathway_name_to_return,
        "level": level,
        "project_code": log.project_code,
        "Media_URL": log.media.url if log.media else ""
    }

    return jsonify(success=True, log=log_data)


@speech_logs_bp.route('/speech_log/update/<int:log_id>', methods=['POST'])
@login_required
def update_speech_log(log_id):
    """
    Updates a speech log with new data from the edit modal.
    """
    log = SessionLog.query.options(
        joinedload(SessionLog.owner),
        joinedload(SessionLog.session_type),
        joinedload(SessionLog.project)
    ).get_or_404(log_id)

    # Permission Checks
    current_user_contact_id = current_user.Contact_ID if current_user.is_authenticated else None
    if not is_authorized(Permissions.SPEECH_LOGS_EDIT_ALL):
        is_owner = (current_user_contact_id == log.Owner_ID)
        if not (is_authorized(Permissions.SPEECH_LOGS_VIEW_OWN) and is_owner):
            return jsonify(success=False, message="Permission denied. You can only edit your own speech logs."), 403

    data = request.get_json()
    media_url = data.get('media_url') or None
    project_id = data.get('project_id')
    
    # Pre-fetch project if needed for duration logic
    updated_project = None
    if project_id and project_id not in [None, "", "null"]:
        updated_project = db.session.get(Project, project_id)

    # 1. Update Basic Fields
    if 'session_title' in data:
        log.Session_Title = data['session_title'] or (updated_project.Project_Name if updated_project else None)

    # 2. Use Model Methods for Complex logic
    log.update_media(media_url)
    
    # RULE: SessionLog.pathway MUST only store pathway-type paths (e.g., "Presentation Mastery").
    # For Presentations, we force use of the owner's main pathway-type path, 
    # even if a "Series" (presentation-type path) was selected in the modal for project lookup.
    is_presentation = updated_project.is_presentation if updated_project else (log.project.is_presentation if log.project else False)
    
    pathway_val = data.get('pathway')
    if is_presentation:
        if log.owner and log.owner.Current_Path:
            pathway_val = log.owner.Current_Path
    elif not pathway_val and log.owner and log.owner.Current_Path:
        pathway_val = log.owner.Current_Path
        
    if pathway_val:
        log.update_pathway(pathway_val)

    log.update_durations(data, updated_project)
    
    # 3. Derive Project Code
    log.project_code = log.derive_project_code()

    try:
        db.session.commit()
        
        # 4. Get response data from model
        summary = log.get_summary_data()

        return jsonify(
            success=True,
            session_title=log.Session_Title,
            project_name=summary['project_name'],
            project_code=summary['project_code'],
            pathway=summary['pathway'],
            project_id=log.Project_ID,
            duration_min=log.Duration_Min,
            duration_max=log.Duration_Max,
            media_url=media_url
        )

    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@speech_logs_bp.route('/speech_log/suspend/<int:log_id>', methods=['POST'])
@login_required
def suspend_speech_log(log_id):
    if not is_authorized(Permissions.SPEECH_LOGS_EDIT_ALL):
        return jsonify(success=False, message="Permission denied"), 403

    log = SessionLog.query.get_or_404(log_id)
    log.Status = 'Delivered'
    try:
        db.session.commit()
        
        # Calculate new progress HTML
        # We need the level of this log to know which section to update
        # Re-fetch log to ensure we have fresh data if needed, though we have it locally
        
        # Determine the display level of this log
        # We need the pathway cache logic or just trust the project's level
        display_level = 1
        pathway_cache = build_pathway_project_cache(project_ids=[log.Project_ID]) if log.Project_ID else {}
        display_level, _, _ = log.get_display_level_and_type(pathway_cache)
        
        progress_html = _get_level_progress_html(log.Owner_ID, display_level)
        
        return jsonify(success=True, level=display_level, progress_html=progress_html)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500




@speech_logs_bp.route('/speech_log/complete/<int:log_id>', methods=['POST'])
@login_required
def complete_speech_log(log_id):
    log = SessionLog.query.get_or_404(log_id)

    current_user_contact_id = current_user.Contact_ID if current_user.is_authenticated else None

    if not is_authorized(Permissions.SPEECH_LOGS_EDIT_ALL):
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
            
        if log.Owner_ID:
            from .utils import sync_contact_metadata
            sync_contact_metadata(log.Owner_ID)
            
        # Calculate new progress HTML
        display_level = 1
        pathway_cache = build_pathway_project_cache(project_ids=[log.Project_ID]) if log.Project_ID else {}
        display_level, _, _ = log.get_display_level_and_type(pathway_cache)
        
        progress_html = _get_level_progress_html(log.Owner_ID, display_level)
            
        return jsonify(success=True, level=display_level, progress_html=progress_html)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500
