# innoeduke/vpemaster/vpemaster-dev0.3/speech_logs_routes.py
from flask import Blueprint, jsonify, render_template, request, session, current_app
from . import db
from .models import SessionLog, Contact, Project, User, SessionType, Media, Role, Pathway, PathwayProject, LevelRole, Achievement
from .auth.utils import login_required, is_authorized
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
    can_view_all = is_authorized('SPEECH_LOGS_VIEW_ALL')
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
        return Contact.query.get(int(speaker_id))
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
    ).join(SessionType).join(Role, SessionType.role_id == Role.id).filter(
        Role.name.isnot(None),
        Role.name != '',
        Role.type.in_(['standard', 'club-specific'])
    )
    
    if filters['speaker_id']:
        base_query = base_query.filter(SessionLog.Owner_ID == filters['speaker_id'])
    if filters['meeting_number']:
        base_query = base_query.filter(SessionLog.Meeting_Number == filters['meeting_number'])
    if filters['role']:
        base_query = base_query.filter(Role.name == filters['role'])
    
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
        if log.session_type and log.session_type.Title == 'Presentation' and log.Project_ID:
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
                elif lr.role.lower() == 'speech' and hasattr(log, 'log_type') and log.log_type == 'speech':
                    if pp_mapping.get(log.Project_ID) == 'required' or not pp_mapping:
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
            contact = Contact.query.get(int(speaker_id))
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
    """Fetch role icons and series initials for template."""
    pathways_db = Pathway.query.filter_by(status='active').order_by(Pathway.name).all()
    series_initials = {p.name: p.abbr for p in pathways_db if p.abbr}
    
    all_roles_db = Role.query.all()
    role_icons = {
        r.name: r.icon or current_app.config['DEFAULT_ROLE_ICON']
        for r in all_roles_db
    }
    
    roles_config = {
        r.name.upper().replace(' ', '_').replace('-', '_'): {
            'name': r.name,
            'icon': r.icon,
            'award': r.award_category,
            'unique': r.is_distinct
        } for r in all_roles_db
    }
    
    return series_initials, role_icons, roles_config


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
    series_initials, role_icons, roles_config = _get_role_metadata()
    
    # 11. Render template
    return render_template(
        'speech_logs.html',
        grouped_logs=sorted_grouped_logs,
        roles_config=roles_config,
        roles=dropdown_data['roles'],
        role_icons=role_icons,
        meeting_numbers=dropdown_data['meeting_numbers'],
        speakers=dropdown_data['speakers'],
        pathways=dropdown_data['pathways'],
        levels=range(1, 6),
        completed_levels=completed_levels,
        projects=dropdown_data['projects'],
        series_initials=series_initials,
        today_date=datetime.today().date(),
        level_roles=LevelRole.query.order_by(LevelRole.level, LevelRole.type).all(),
        completion_summary=completion_summary,
        selected_filters=filters,
        is_member_view=is_member_view,
        can_view_all=can_view_all,
        view_mode=view_mode,
        pathway_mapping=dropdown_data['pathway_mapping'],
        all_contacts=dropdown_data['all_contacts'],
        impersonated_user_name=pathway_info['impersonated_user_name'],
        viewed_contact=viewed_contact,
        member_pathways=pathway_info['member_pathways'],
        active_level=active_level,
        GENERIC_PROJECT_ID=ProjectID.GENERIC
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
        # Check project_code first
        if log.project_code:
            match = re.match(r"([A-Z]+)(\d+)", log.project_code)
            if match:
                abbr = match.group(1)
                level = int(match.group(2))
                log.project_code = log.project_code
                
                pathway_db = Pathway.query.filter_by(abbr=abbr).first()
                if pathway_db:
                    pathway_name_to_return = pathway_db.name

        if not getattr(log, 'project_code', None):
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
                if log.project and log.project.is_generic: # Generic
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
    log = SessionLog.query.options(
        joinedload(SessionLog.owner),
        joinedload(SessionLog.session_type),
        joinedload(SessionLog.project)
    ).get_or_404(log_id)

    # Permission Checks
    current_user_contact_id = current_user.Contact_ID if current_user.is_authenticated else None
    if not is_authorized('SPEECH_LOGS_EDIT_ALL'):
        is_owner = (current_user_contact_id == log.Owner_ID)
        if not (is_authorized('SPEECH_LOGS_VIEW_OWN') and is_owner):
            return jsonify(success=False, message="Permission denied. You can only edit your own speech logs."), 403

    data = request.get_json()
    media_url = data.get('media_url') or None
    project_id = data.get('project_id')
    
    # Pre-fetch project if needed for duration logic
    updated_project = None
    if project_id and project_id not in [None, "", "null"]:
        updated_project = Project.query.get(project_id)

    # 1. Update Basic Fields
    if 'session_title' in data:
        log.Session_Title = data['session_title'] or (updated_project.Project_Name if updated_project else None)

    # 2. Use Model Methods for Complex logic
    log.update_media(media_url)
    
    # REQUIREMENT: For presentations, use owner's current path to fill pathway field
    is_presentation = (log.session_type and log.session_type.Title == 'Presentation')
    if is_presentation and log.owner and log.owner.Current_Path:
        log.pathway = log.owner.Current_Path
    elif 'pathway' in data:
        log.update_pathway(data['pathway'])

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
