# innoeduke/vpemaster/vpemaster-dev0.3/speech_logs_routes.py
from flask import Blueprint, jsonify, render_template, request, session, current_app
from . import db
from .models import SessionLog, Contact, Project, User, SessionType, Media, MeetingRole, Pathway, PathwayProject, LevelRole, Achievement, Meeting, OwnerMeetingRoles
from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
from .club_context import authorized_club_required
from flask_login import current_user
from .utils import (
    get_project_code, 
    build_pathway_project_cache, 
    normalize_role_name, 
    get_role_aliases,
    get_dropdown_metadata,
    get_meetings_by_status,
    get_level_project_requirements
)
from sqlalchemy import distinct, or_
from sqlalchemy.orm import joinedload
from datetime import datetime
import re
from .constants import ProjectID

speech_logs_bp = Blueprint('speech_logs_bp', __name__)


@speech_logs_bp.before_request
def check_journal_enabled():
    from flask import request
    # Allow details fetching and speech updating to bypass the Journal module check,
    # as these are required for editing speech details from core/agenda pages.
    if request.endpoint and (request.endpoint.endswith('.get_speech_log_details') or request.endpoint.endswith('.update_speech_log')):
        return

    from app.club_context import is_module_enabled
    from flask import abort
    if not is_module_enabled('Journal'):
        abort(404)


# ============================================================================
# PRIVATE HELPER FUNCTIONS
# ============================================================================

def _attach_owners(logs):
    """
    Performance optimization: Pre-fetch all owners for a list of session logs 
    to avoid N+1 queries via log.owners property.
    """
    if not logs:
        return
        
    log_ids = [l.id for l in logs]
    
    # 1. Fetch owners for single-owner roles (linked via session_log_id)
    omr_entries = db.session.query(OwnerMeetingRoles, Contact).join(Contact).filter(
        OwnerMeetingRoles.session_log_id.in_(log_ids)
    ).all()
    
    owners_by_log = {}
    for omr, contact in omr_entries:
        if omr.session_log_id not in owners_by_log:
            owners_by_log[omr.session_log_id] = []
        owners_by_log[omr.session_log_id].append(contact)
        
    # 2. Fetch owners for shared roles (linked via meeting_id and role_id)
    # Identify shared logs
    shared_logs = [l for l in logs if l.session_type and l.session_type.role and not l.session_type.role.has_single_owner]
    if shared_logs:
        # Get unique (meeting_id, role_id) pairs
        shared_keys = set()
        for l in shared_logs:
            if l.meeting:
                shared_keys.add((l.meeting.id, l.session_type.role_id))
        
        if shared_keys:
            from sqlalchemy import or_
            filter_conds = [
                db.and_(OwnerMeetingRoles.meeting_id == m_id, OwnerMeetingRoles.role_id == r_id)
                for m_id, r_id in shared_keys
            ]
            
            omr_shared = db.session.query(OwnerMeetingRoles, Contact).join(Contact).filter(
                OwnerMeetingRoles.session_log_id.is_(None),
                or_(*filter_conds)
            ).all()
            
            shared_owners_lookup = {}
            for omr, contact in omr_shared:
                key = (omr.meeting_id, omr.role_id)
                if key not in shared_owners_lookup:
                    shared_owners_lookup[key] = []
                shared_owners_lookup[key].append(contact)
            
            # Map back to logs
            for l in shared_logs:
                key = (l.meeting.id, l.session_type.role_id)
                if key in shared_owners_lookup:
                    if l.id not in owners_by_log:
                        owners_by_log[l.id] = []
                    # Avoid duplicates if any
                    owners_by_log[l.id].extend(shared_owners_lookup[key])

    # 3. Attach to logs via the new _cached_owners attribute
    # Improved: Also attach historical credentials found in OwnerMeetingRoles
    
    # helper to map targets: {session_log_id: {contact_id: {pathway, level}}}
    targets_map = {}
    for omr, contact in omr_entries:
        if omr.session_log_id not in targets_map:
            targets_map[omr.session_log_id] = {}
        targets_map[omr.session_log_id][contact.id] = {
            'pathway': omr.target_pathway,
            'level': omr.target_level
        }

    # Shared roles targets
    if 'omr_shared' in locals():
        for omr, contact in omr_shared:
            # For shared roles, we can't key by log ID easily until we map back
            # But we can update the map for each log that matches
            key = (omr.meeting_id, omr.role_id)
            for l in shared_logs:
                if (l.meeting.id, l.session_type.role_id) == key:
                    if l.id not in targets_map:
                        targets_map[l.id] = {}
                    targets_map[l.id][contact.id] = {
                        'pathway': omr.target_pathway,
                        'level': omr.target_level
                    }

    for l in logs:
        l._cached_owners = owners_by_log.get(l.id, [])
        l._cached_owner_targets = targets_map.get(l.id, {})


def _search_logs(query_str, can_view_all, current_club_id):
    """
    Search session logs matching the given query string.
    Supports multiple keywords (AND combination of OR clauses for each keyword).
    """
    if not query_str:
        return []
        
    keywords = query_str.strip().split()
    if not keywords:
        return []
        
    # Start with base query for the current club
    query = db.session.query(SessionLog).options(
        joinedload(SessionLog.media),
        joinedload(SessionLog.session_type).joinedload(SessionType.role),
        joinedload(SessionLog.meeting),
        joinedload(SessionLog.project)
    ).join(SessionType).join(MeetingRole).join(Meeting, SessionLog.meeting_id == Meeting.id).filter(
        MeetingRole.name.isnot(None),
        MeetingRole.name != '',
        MeetingRole.type.in_(['standard', 'club-specific']),
        Meeting.club_id == current_club_id
    )
    
    # Outer join to retrieve owners
    query = query.outerjoin(
        OwnerMeetingRoles,
        or_(
            SessionLog.id == OwnerMeetingRoles.session_log_id,
            db.and_(
                OwnerMeetingRoles.session_log_id.is_(None),
                SessionLog.meeting_id == OwnerMeetingRoles.meeting_id,
                SessionType.role_id == OwnerMeetingRoles.role_id
            )
        )
    ).outerjoin(
        Contact,
        OwnerMeetingRoles.contact_id == Contact.id
    )
    
    # Outer join to retrieve Pathway and PathwayProject for dynamically constructed project codes
    query = query.outerjoin(PathwayProject, SessionLog.Project_ID == PathwayProject.project_id) \
                 .outerjoin(Pathway, PathwayProject.path_id == Pathway.id)
    
    # Add guest check (if user is guest of the active club, restrict finished meetings)
    try:
        if current_user.is_guest_of_club(current_club_id):
            query = query.filter(Meeting.status != 'finished')
    except (RuntimeError, AttributeError):
        # No request context (helper called from tests) — skip the gate.
        pass
        
    # Build the filters for each keyword
    for kw in keywords:
        kw_like = f"%{kw}%"
        
        # Build conditions for this keyword
        conds = [
            Contact.Name.like(kw_like),
            Contact.first_name.like(kw_like),
            Contact.last_name.like(kw_like),
            SessionLog.Session_Title.like(kw_like),
            MeetingRole.name.like(kw_like),
            SessionType.Title.like(kw_like),
            SessionLog.project_code.like(kw_like),
            db.cast(Meeting.Meeting_Number, db.String).like(kw_like),
            db.func.concat(db.func.coalesce(Pathway.abbr, ''), db.func.coalesce(PathwayProject.code, '')).like(kw_like)
        ]
        
        query = query.filter(or_(*conds))
        
    # Retrieve all matched logs, order by meeting number desc
    results = query.order_by(Meeting.Meeting_Number.desc()).all()
    
    return results


def _get_view_settings():
    """
    Determine view permissions and mode.
    Returns: (can_view_all, view_mode, is_member_view)
    """
    can_view_all = is_authorized(Permissions.SPEECH_LOGS_MANAGE)
    view_mode = request.args.get('view_mode', 'member')
    
    if view_mode == 'admin':
        view_mode = 'member'
        
    q = request.args.get('q', '').strip()
    if q and can_view_all:
        view_mode = 'search'
        
    is_member_view = (view_mode in ('member', 'search'))
    
    return can_view_all, view_mode, is_member_view


def _parse_filters(is_member_view, can_view_all):
    """
    Parse request arguments into filter dictionary.
    Returns: dict with filter values
    """
    filters = {
        'meeting_id': request.args.get('meeting_id'),
        'pathway': request.args.get('pathway'),
        'level': request.args.get('level'),
        'speaker_id': request.args.get('speaker_id'),
        'status': request.args.get('status'),
        'role': request.args.get('role')
    }

    # Handle speaker_id for member view
    if is_member_view:
        can_view_other_members = is_authorized(Permissions.ROSTER_VIEW) or can_view_all
        is_authorized_speaker = False
        
        if can_view_other_members and filters['speaker_id']:
            if can_view_all:
                is_authorized_speaker = True
            else:
                from .club_context import get_current_club_id
                from .models.contact_club import ContactClub
                club_id = get_current_club_id()
                try:
                    target_speaker_id = int(filters['speaker_id'])
                    contact = Contact.query.join(ContactClub).filter(
                        ContactClub.club_id == club_id,
                        Contact.id == target_speaker_id,
                        Contact.Type == 'Member'
                    ).first()
                    if contact:
                        is_authorized_speaker = True
                except (ValueError, TypeError):
                    pass
                    
        if is_authorized_speaker:
            # Keep the requested speaker_id
            pass
        else:
            from .club_context import get_current_club_id
            club_id = get_current_club_id()
            contact = current_user.get_contact(club_id) if current_user.is_authenticated else None
            
            if contact:
                filters['speaker_id'] = contact.id
            else:
                filters['speaker_id'] = -1
                
                # Fallback: Try to find ANY contact for this user
                # This handles cases where user is viewing logs while in a non-home context
                any_uc = current_user.get_user_club(None)
                if any_uc and any_uc.contact:
                    filters['speaker_id'] = any_uc.contact.id
    

    return filters


def _get_viewed_contact(speaker_id):
    """
    Get contact object for the speaker being viewed.
    Returns: Contact object or None
    """
    if not speaker_id or speaker_id == -1:
        return None
    
    try:
        contact = db.session.get(Contact, int(speaker_id))
        if contact:
            # contact.user_id is now a property that calculates the ID automatically
            return contact
        return contact
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
        if selected_pathway and selected_pathway not in ('all', 'Non Pathway'):
            if not any(p['name'] == selected_pathway for p in member_pathways):
                member_pathways.append({'name': selected_pathway, 'status': 'unknown', 'abbr': '', 'path_id': None})
                member_pathways.sort(key=lambda x: x['name'])
    return {
        'selected_pathway': selected_pathway,
        'member_pathways': member_pathways,
        'impersonated_user_name': viewed_contact.Name if viewed_contact else None
    }


def _get_pathway_date_range(contact, pathway_name):
    """
    Determine the valid date range for a pathway based on achievement history.
    Returns: (start_date, end_date)
    - start_date: Day AFTER previous path completion (or min date)
    - end_date: Path completion date (or max date if current)
    """
    if not contact or not pathway_name or pathway_name == 'all':
        return None, None
        
    if pathway_name == 'Non Pathway':
        return datetime.min.date(), datetime.max.date()
        
    # Get all path completions sorted by date
    uid = getattr(contact, 'user_id', None)
    if uid:
        achievements = Achievement.query.filter_by(
            user_id=uid,
            achievement_type='path-completion'
        ).order_by(Achievement.issue_date).all()
    else:
        # Fall back to member_id if no user_id
        achievements = Achievement.query.filter_by(
            member_id=str(contact.id),
            achievement_type='path-completion'
        ).order_by(Achievement.issue_date).all()
    
    # Identify segments
    start_date = datetime.min.date()
    end_date = None
    
    found_path = False
    
    for ach in achievements:
        if ach.path_name == pathway_name:
            end_date = ach.issue_date
            found_path = True
            break
        # If we haven't found our path yet, this achievement marks the END of a previous segment,
        # so our path must start AFTER this.
        start_date = ach.issue_date # We'll start checking from day after usually, but inclusive logic is safer if same day switch
    
    # Refine start_date logic: strictly speaking, roles for a new path 
    # shouldn't overlap with the *completion* event of the old one, but 
    # in practice, same-day transition is possible. 
    # Let's keep it inclusive of the boundary for now or add 1 day if precise.
    
    if found_path:
        return start_date, end_date
    
    # If not found in COMPLETED paths, check if it is the CURRENT path
    if contact.Current_Path == pathway_name:
        # Relaxed logic: Allow current path to see ALL history (start from min date)
        # This fixes the issue where generic roles from before the previous path completion
        # were hidden from the current path.
        return datetime.min.date(), datetime.max.date()
        
    # If neither completed nor current, it's not a valid active segment for generic roles
    return None, None






def _get_path_progress_data(completion_summary=None):
    """
    Fetch and structure path progress data (Matrix of Levels x Bands).
    Enriches with completion status from completion_summary if provided.
    Returns: list of row dictionaries for the template.
    """
    level_roles = LevelRole.query.all()
    
    # 1. Group roles by (level, band)
    bands = set()
    levels = set()
    matrix = {}
    
    for lr in level_roles:
        lvl = lr.level
        bnd = lr.band if lr.band is not None else 0
        
        levels.add(lvl)
        bands.add(bnd)
        
        if lvl not in matrix:
            matrix[lvl] = {}
        
        if bnd not in matrix[lvl]:
            matrix[lvl][bnd] = []
            
        matrix[lvl][bnd].append(lr)
    
    sorted_levels = sorted(list(levels))
    sorted_bands = sorted(list(bands))
    
    # 2. Build rows for template
    data_rows = []
    
    # Helper to find role status in summary
    def get_role_status(level, role_name, role_type):
        if not completion_summary:
            return None
            
        summ_lvl = completion_summary.get(str(level))
        if not summ_lvl:
            return None
            
        group_key = 'elective' if role_type == 'elective' else 'required'
        items = summ_lvl.get(group_key, [])
        
        for item in items:
            if item['role'] == role_name:
                return item
        return None

    for lvl in sorted_levels:
        row_bands = []
        for bnd in sorted_bands:
            roles = matrix.get(lvl, {}).get(bnd, [])
            roles.sort(key=lambda x: x.role) 
            
            # Determine if this band is purely elective
            is_band_elective = all(r.type == 'elective' for r in roles) if roles else False
            
            # Enrich roles with completion data
            enriched_roles = []
            for r in roles:
                status_data = get_role_status(lvl, r.role, r.type)
                r.completion_data = status_data # Attach runtime data
                enriched_roles.append(r)
                
            row_bands.append({
                'band': bnd, 
                'roles': enriched_roles,
                'is_elective': is_band_elective
            })
            
        extra_roles = []
        speeches = []
        if completion_summary and str(lvl) in completion_summary:
            extra_roles = completion_summary[str(lvl)].get('extra_roles', [])
            speeches = completion_summary[str(lvl)].get('speeches', [])
            
        data_rows.append({
            'level': lvl, 
            'bands': row_bands,
            'extra_roles': extra_roles,
            'speeches': speeches
        })
        
    return data_rows


def _fetch_logs_with_filters(filters):
    """
    Build and execute query for session logs with filters.
    Returns: list of SessionLog objects
    """
    from .club_context import get_current_club_id
    from .services.role_service import RoleService
    current_club_id = get_current_club_id()
    
    # NEW logic: If filtering by speaker, use RoleService as source of truth for their duties
    if filters['speaker_id'] and filters['speaker_id'] != -1:
        # Fetch directly assigned roles (booked or completed)
        logs = RoleService.get_roles_for_contact(filters['speaker_id'], club_id=None)
        
        # Fetch roles the user is waitlisted for
        waitlist_logs = RoleService.get_waitlist_for_contact(filters['speaker_id'], club_id=None)
        logs.extend(waitlist_logs)

        # Filter out officer roles (SAA, President, etc.)
        logs = [l for l in logs if not (l.session_type and l.session_type.role and l.session_type.role.type == 'officer')]
        
        # Verify that each log actually has the speaker_id as an owner
        # This ensures no cross-contamination between users' logs
        try:
            speaker_id_int = int(filters['speaker_id'])
            filtered_logs = []
            for log in logs:
                # Check if speaker_id is in the list of owners for this log
                owner_ids = [o.id for o in (log.owners if hasattr(log, 'owners') else [])]
                if speaker_id_int in owner_ids:
                    filtered_logs.append(log)
            logs = filtered_logs
        except (ValueError, TypeError):
            pass

        # Apply remaining filters (meeting_id, role) manually
        if filters['meeting_id']:
            logs = [l for l in logs if str(l.meeting_id) == str(filters['meeting_id'])]
        if filters['role']:
            logs = [l for l in logs if l.session_type and l.session_type.role and l.session_type.role.name == filters['role'] or l.session_type and l.session_type.Title == filters['role']]
            
        # Restriction for Guest: cannot view finished meetings (though usually guests won't have duties)
        try:
            if current_user.is_guest_of_club(current_club_id):
                logs = [l for l in logs if l.meeting and l.meeting.status != 'finished']
        except (RuntimeError, AttributeError):
            pass
             
        return logs

    # Legacy/Admin logic for viewing ALL logs
    base_query = db.session.query(SessionLog).options(
        joinedload(SessionLog.media),
        joinedload(SessionLog.session_type).joinedload(SessionType.role),
        joinedload(SessionLog.meeting),
        joinedload(SessionLog.project)
    ).join(SessionType).join(MeetingRole).join(Meeting, SessionLog.meeting_id == Meeting.id).filter(
        MeetingRole.name.isnot(None),
        MeetingRole.name != '',
        MeetingRole.type.in_(['standard', 'club-specific']),
        Meeting.club_id == current_club_id
    )
    
    # Restriction for Guest: cannot view finished meetings
    try:
        if current_user.is_guest_of_club(current_club_id):
            base_query = base_query.filter(Meeting.status != 'finished')
    except (RuntimeError, AttributeError):
        pass
    
    if filters['meeting_id']:
        base_query = base_query.filter(SessionLog.meeting_id == filters['meeting_id'])
    if filters['role']:
        base_query = base_query.filter(or_(MeetingRole.name == filters['role'], SessionType.Title == filters['role']))
    
    results = base_query.order_by(Meeting.Meeting_Number.desc()).all()
    return results


def _process_logs(all_logs, filters, pathway_cache, view_mode='member'):
    """
    Process logs: determine type/level, apply filters, group by level or category.
    Returns: dict of grouped logs {group_key: [logs]}
    """
    grouped_logs = {}
    processed_roles = set()
    
    # Calculate date range for the selected pathway filter
    p_filter = filters.get('pathway')
    path_start_date, path_end_date = None, None
    
    # We need a context contact for this. If filtering by speaker, use that.
    # Otherwise, we might rely on individual log owners (complex).
    # Assuming member view focus primarily:
    context_contact_id = filters.get('speaker_id')
    context_contact = None
    if context_contact_id and context_contact_id != -1:
        context_contact = _get_viewed_contact(context_contact_id)
        
    if context_contact and p_filter and p_filter != 'all':
        path_start_date, path_end_date = _get_pathway_date_range(context_contact, p_filter)

    for log in all_logs:
        # Determine the best owner for display in this context if not already set by RoleService
        if not getattr(log, 'context_owner', None):
            speaker_id = filters.get('speaker_id')
            log.context_owner = None
            if speaker_id:
                try:
                    sid_int = int(speaker_id)
                    for o in log.owners:
                        if o.id == sid_int:
                            log.context_owner = o
                            break
                except (ValueError, TypeError):
                    pass
            
            if not log.context_owner:
                log.context_owner = log.owner

        # Use model method to get display level and type
        # Pass the current filtered pathway to ensure correct level/labeling
        p_filter = filters.get('pathway')
        context_path = p_filter if p_filter and p_filter != 'all' else None
        
        # Determine context target for the owner
        context_target = None
        if log.context_owner and hasattr(log, '_cached_owner_targets'):
             context_target = log._cached_owner_targets.get(log.context_owner.id)

        # We set it on the log so it can be used for display and logic
        log.context_target = context_target

        # Override context_path if target pathway is set for this role
        if context_target and context_target.get('pathway'):
            # Only override if we aren't explicitly filtering by another pathway
            # Or perhaps target_pathway IS the pathway for this role, so it should be the display pathway
            if not context_path or context_path == 'all':
                context_path = context_target.get('pathway')

        # Filter by target_pathway from owner_meeting_roles
        if p_filter and p_filter != 'all':
            target_pathway = context_target.get('pathway') if context_target else None
            if p_filter == 'Non Pathway':
                # "Non Pathway" means show only logs where target_pathway is NULL, empty, or "Non Pathway"
                if target_pathway not in (None, '', 'Non Pathway'):
                    continue
            else:
                # For specific pathways, only show if target_pathway matches
                if target_pathway != p_filter:
                    continue

        display_level, log_type, project_code = log.get_display_level_and_type(
            pathway_cache, 
            context_contact=log.context_owner,
            context_pathway_name=context_path
        )
        
        # Store for filtering
        log.display_level = display_level
        log.log_type = log_type
        log.project_code = project_code
        
        # Determine display pathway:
        # For roles: context (filter) > context_owner.Current_Path > log.pathway (snapshot)
        # For speeches: log.pathway (snapshot) > context (filter) > context_owner.Current_Path
        if log_type == 'role':
            log.display_pathway = context_path or (log.context_owner.Current_Path if log.context_owner else log.pathway)
        else:
            log.display_pathway = log.pathway or context_path or (log.context_owner.Current_Path if log.context_owner else None)
        
        # Identify Presentation Series
        # Updated to check project property instead of session type title
        if log.project and log.project.is_presentation:
             if pathway_cache and log.Project_ID in pathway_cache:
                  pp_data = pathway_cache[log.Project_ID]
                  
                  # Find best match for presentation series
                  best_pp = None
                  if context_path:
                      # Try to find exactly matching pathway name
                      for pp in pp_data.values():
                          if pp.pathway and pp.pathway.name == context_path:
                              best_pp = pp
                              break
                  
                  if not best_pp:
                      # Original fallback loop
                      for pp in pp_data.values():
                           # Check if pathway is of type 'presentation' or contains Series in name
                           p_type = (pp.pathway.type or '').lower()
                           if 'presentation' in p_type or 'series' in pp.pathway.name.lower():
                               best_pp = pp
                               break
                  
                  if best_pp:
                       log.presentation_series = best_pp.pathway.name
                       log.presentation_code = best_pp.code
                       log.log_type = 'presentation'
        
        # Deduplicate roles
        if log_type == 'role' and not log.Project_ID:
            owner_id = log.context_owner.id if log.context_owner else (log.owner.id if log.owners else None)
            
            role_name = log.session_type.role.name if log.session_type and log.session_type.role else log.session_type.Title
            dedup_key = (log.Meeting_Number, owner_id, role_name)
            
            if dedup_key in processed_roles:
                continue
            processed_roles.add(dedup_key)
        
        # Apply filters using model method
        if view_mode != 'search' and not log.matches_filters(
            pathway=filters['pathway'],
            level=filters['level'],
            status=filters['status'],
            log_type=log_type
        ):
            continue
            
        # Additional Date-Based Filter for Generic Roles
        # If it's a generic role (no project ID) and we have a pathway filter active
        if view_mode != 'search' and log_type == 'role' and not log.Project_ID and filters['pathway'] and filters['pathway'] != 'all':
            # Strict mode: If date range is None (path not found/valid), hide generic roles
            if path_start_date is None and path_end_date is None:
                 continue
                 
            # Check meeting date against range
            if log.meeting and log.meeting.Meeting_Date:
                m_date = log.meeting.Meeting_Date
                # Ensure date comparison works (convert to date if needed, though simple comparison usually works for date/datetime)
                # m_date is typically datetime.date in Model
                
                if not (path_start_date <= m_date <= path_end_date):
                    continue
        
        # Special check for speeches without project
        if view_mode != 'search' and filters['pathway'] and log_type == 'speech' and not log.Project_ID:
            continue
        
        # Add to group
        if view_mode == 'search':
            group_key = 'Search Results'
        elif view_mode == 'admin':
            # Group by Award Category for Meeting View
            category = 'Other'
            if log.session_type and log.session_type.role and log.session_type.role.award_category:
                category = log.session_type.role.award_category
            elif log.log_type == 'speech' or log.log_type == 'presentation':
                 # Fallback for speeches if role category is missing (though Prepared Speaker usually has it)
                 category = 'speaker'
            
            group_key = category
        else:
            # Group by Level for Member View
            group_key = display_level

        if group_key not in grouped_logs:
            grouped_logs[group_key] = []
        grouped_logs[group_key].append(log)
    
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
    
    def get_group_sort_key(group_key):
        # Priority for categories in Meeting View
        category_priority = {
            'speaker': 1,
            'evaluator': 2,
            'table-topic': 3,
            'role-taker': 4,
            'Other': 99
        }
        
        if group_key in category_priority:
            return (category_priority.get(group_key, 99), group_key)
            
        # Fallback to Level sorting for Member View
        try:
            return (0, -int(group_key))
        except (ValueError, TypeError):
            return (1, group_key)
    
    for group_key in grouped_logs:
        grouped_logs[group_key].sort(key=get_activity_sort_key)
        
        # Consolidate role logs
        consolidated_group = []
        role_group_map = {}
        
        for item in grouped_logs[group_key]:
            if item.log_type == 'role' and not item.Project_ID:
                role_name = item.session_type.role.name if item.session_type and item.session_type.role else item.session_type.Title
                owner_id = item.context_owner.id if item.context_owner else (item.owner.id if item.owners else None)
                key = (owner_id, role_name)
                
                if key in role_group_map:
                    role_group_map[key]['logs'].append(item)
                else:
                    new_group = {
                        'log_type': 'grouped_role',
                        'role_name': role_name,
                        'session_type': item.session_type,
                        'owner': item.context_owner or item.owner,
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
        
        grouped_logs[group_key] = final_list
    
    # Sort groups
    sorted_grouped_logs = dict(
        sorted(grouped_logs.items(), key=lambda item: get_group_sort_key(item[0]))
    )
    
    return sorted_grouped_logs


def _status_priority(s):
    """Priority: completed < booked < waitlist < pending"""
    return {'completed': 0, 'booked': 1, 'waitlist': 2, 'pending': 3}.get(s, 4)


def _process_band_requirements(level_str, band_reqs, logs_for_level, used_log_ids, pp_mapping, role_aliases, summary):
    """
    Process requirements for a specific band of roles.
    Updates the level summary dictionary in place.
    """
    # Determine group type
    is_elective_band = all(lr.type == 'elective' for lr in band_reqs)
    
    band_completions = 0
    band_quota = 0
    
    # Band Quota Logic
    if is_elective_band:
        lvl = int(level_str)
        band_quota = 1 if lvl <= 4 else 2
        summary['elective_required'] += band_quota
    else:
        band_quota = sum(lr.count_required for lr in band_reqs)

    # For each role in the band
    for lr in band_reqs:
        role_count = 0
        role_details = []
        
        for entry in logs_for_level:
            items_to_process = entry['logs'] if isinstance(entry, dict) and entry.get('log_type') == 'grouped_role' else [entry]
            
            for log in items_to_process:
                if log.id in used_log_ids:
                    continue
                
                satisfied = False
                
                # Descriptive logic for project and session
                has_real_project = log.Project_ID and log.Project_ID != ProjectID.GENERIC
                project_name = log.project.Project_Name if log.project else None
                session_title = log.Session_Title
                
                # Determine name for history/tooltip
                if project_name and session_title:
                    item_name = f"{project_name} ({session_title})"
                elif project_name:
                    item_name = project_name
                elif session_title:
                    item_name = session_title
                else:
                    item_name = log.session_type.Title if log.session_type else "Activity"
                
                # Determine if we show the project code
                display_code = log.project_code if hasattr(log, 'project_code') else None
                if display_code:
                    match = re.match(r"^[A-Z]+\d+$", display_code)
                    if match and not has_real_project:
                        display_code = None
                
                item_name_with_code = f"{display_code} {item_name}" if display_code else item_name
                
                actual_role_name = (log.session_type.role.name if log.session_type and log.session_type.role else (log.session_type.Title if log.session_type else "")).strip().lower()
                target_role_name = lr.role.strip().lower()
                
                norm_actual = normalize_role_name(actual_role_name)
                norm_target = normalize_role_name(target_role_name)
                
                is_role_match = (norm_actual == norm_target)
                if not is_role_match and role_aliases.get(norm_actual) == norm_target:
                    is_role_match = True
                
                if is_role_match:
                    satisfied = True
                elif actual_role_name == 'club-specific' or (log.session_type and log.session_type.role and log.session_type.role.type == 'club-specific'):
                    if norm_target == normalize_role_name('Club Specific*'):
                        satisfied = True
                elif lr.role.lower() == 'speech' and hasattr(log, 'log_type') and (log.log_type == 'speech' or log.log_type == 'presentation'):
                    if log.log_type == 'presentation' or pp_mapping.get(log.Project_ID) == 'required' or not pp_mapping:
                        satisfied = True
                elif hasattr(log, 'presentation_series') and log.presentation_series:
                    if normalize_role_name(log.presentation_series.lower()) == norm_target:
                        satisfied = True
                elif lr.role.lower() == 'elective project' and hasattr(log, 'log_type') and log.log_type == 'speech':
                    if pp_mapping.get(log.Project_ID) == 'elective':
                        satisfied = True
            
                if satisfied:
                    # Determine status
                    is_waitlist = getattr(log, 'is_waitlist', False)
                    meeting_finished = log.meeting and log.meeting.status == 'finished'
                    
                    status = 'pending'
                    if log.Status == 'Completed' or (not is_waitlist and meeting_finished):
                        status = 'completed'
                        role_count += 1
                    elif is_waitlist:
                        status = 'waitlist'
                    else:
                        status = 'booked'

                    role_details.append({
                        'id': log.id,
                        'name': item_name_with_code, 
                        'status': status,
                        'meeting_number': log.Meeting_Number,
                        'meeting_date': log.meeting.Meeting_Date.strftime('%Y-%m-%d') if log.meeting and log.meeting.Meeting_Date else 'N/A',
                        'project_code': display_code,
                        'role_name': (log.session_type.role.name if log.session_type and log.session_type.role else (log.session_type.Title if log.session_type else "Activity")).strip()
                    })
                    used_log_ids.add(log.id)
        
        band_completions += min(role_count, lr.count_required)
        
        # Sort role_details
        role_details.sort(key=lambda x: _status_priority(x['status']))

        history_items = [d for d in role_details if d['status'] in ('completed', 'booked', 'waitlist')]
        
        requirement_items = []
        for i in range(min(len(role_details), lr.count_required)):
            requirement_items.append(role_details[i])
        
        badge_status = 'pending'
        if role_count >= lr.count_required:
            badge_status = 'completed'
        elif len(role_details) > 0:
            badge_status = role_details[0]['status']

        if is_elective_band:
            if len(role_details) > 0:
                item_data = {
                    'role': lr.role,
                    'count': role_count,
                    'required': lr.count_required,
                    'requirement_items': requirement_items,
                    'history_items': history_items,
                    'status': badge_status
                }
                summary['elective'].append(item_data)
        else:
            pending_needed = max(0, lr.count_required - len(requirement_items))
            for i in range(pending_needed):
                requirement_items.append({'name': f"Pending {lr.role}", 'status': 'pending'})
            
            item_data = {
                'role': lr.role,
                'count': role_count,
                'required': lr.count_required,
                'requirement_items': requirement_items,
                'history_items': history_items,
                'status': badge_status
            }
            summary['required'].append(item_data)
            summary['required_count'] += min(role_count, lr.count_required)
            summary['required_total'] += lr.count_required
            if role_count < lr.count_required:
                summary['required_completed'] = False

    if is_elective_band:
        summary['elective_count'] += min(band_completions, band_quota)
        if summary['elective_count'] < summary['elective_required']:
            summary['elective_completed'] = False


def _get_project_groups_for_level(level_int, path_id):
    """
    Fetch and group PathwayProjects for a given level.
    Groups by Major Code (e.g., 1.4) AND Project ID adjacency.
    """
    all_path_projects = PathwayProject.query.filter_by(
        path_id=path_id,
        level=level_int
    ).order_by(PathwayProject.code, PathwayProject.project_id).all() if path_id else []
    
    badge_groups = []
    current_group = []
    current_major = None
    
    for pp in all_path_projects:
        match = re.match(r"(\d+\.\d+)(\.\d+)?", pp.code)
        major_code = match.group(1) if match else pp.code
        
        is_new_group = False
        if not current_group:
            is_new_group = True
        elif pp.type == 'elective':
             is_new_group = True
        elif major_code != current_major:
            is_new_group = True
        elif pp.project_id != current_group[-1].project_id + 1:
            is_new_group = True
        
        if is_new_group:
            if current_group:
                badge_groups.append((current_major, current_group[0].type, current_group))
            current_group = [pp]
            current_major = major_code
        else:
            current_group.append(pp)
    
    if current_group:
        badge_groups.append((current_major, current_group[0].type, current_group))
        
    return badge_groups

def _build_evaluator_map(logs_for_level):
    """Build a map of (meeting_number, speaker_suffix) -> evaluator_name."""
    relevant_meetings = set(log.Meeting_Number for entry in logs_for_level 
                          for log in (entry['logs'] if isinstance(entry, dict) and entry.get('log_type') == 'grouped_role' else [entry]))
    evaluator_map = {}
    if relevant_meetings:
        eval_logs = db.session.query(SessionLog).join(SessionType).join(MeetingRole).join(Meeting, SessionLog.meeting_id == Meeting.id).filter(
            Meeting.Meeting_Number.in_(relevant_meetings),
            MeetingRole.name.like('%Evaluator%')
        ).options(joinedload(SessionLog.session_type).joinedload(SessionType.role)).all()
        _attach_owners(eval_logs)
        for el in eval_logs:
            role_name = el.session_type.role.name
            match = re.search(r'Evaluator\s*(\d+)', role_name, re.IGNORECASE)
            suffix = match.group(1) if match else "1"
            owner_name = el.owner.Name if el.owner else "TBA"
            evaluator_map[(el.Meeting_Number, suffix)] = owner_name
    return evaluator_map

def _process_badge_group(major_code, p_type, rps, logs_for_level, evaluator_map, used_log_ids):
    """
    Process a single badge group (list of PathwayProjects).
    Returns (speech_data, all_completed, has_activity)
    """
    speech_data = {
        'project_id': rps[0].project_id if len(rps) == 1 else None,
        'project_code': major_code,
        'status': 'pending',
        'requirement_items': [],
        'history_items': []
    }
    
    all_completed = True
    has_activity = False
    
    for rp in rps:
        req_item = {'name': f"Project {rp.code}", 'status': 'pending'}
        rp_completed = False
        
        for entry in logs_for_level:
            items = entry['logs'] if isinstance(entry, dict) and entry.get('log_type') == 'grouped_role' else [entry]
            for log in items:
                # Allow using a log even if it is in used_log_ids, IF the log's Project_ID matches the requirement's project_id
                # This covers cases like 1.4.3 (Individual Evaluator) which is both a role and a project
                is_exact_project_match = (log.Project_ID == rp.project_id)
                if log.id in used_log_ids and not is_exact_project_match:
                    continue
                    
                if log.Project_ID == rp.project_id:
                    has_activity = True
                    has_real_project = log.Project_ID and log.Project_ID != ProjectID.GENERIC
                    project_name = log.project.Project_Name if log.project else None
                    session_title = log.Session_Title
                    
                    if project_name and session_title:
                        item_name = f"{project_name} ({session_title})"
                    elif project_name:
                        item_name = project_name
                    elif session_title:
                        item_name = session_title
                    else:
                        item_name = log.session_type.Title if log.session_type else "Activity"
                    
                    display_code = log.project_code if hasattr(log, 'project_code') else None
                    if display_code:
                        match_code = re.match(r"^[A-Z]+\d+$", display_code)
                        if match_code and not has_real_project:
                            display_code = None
                    
                    item_name_with_code = f"{display_code} {item_name}" if display_code else item_name
                    
                    role_name = log.session_type.role.name if log.session_type and log.session_type.role else ""
                    match_speaker = re.search(r'Speaker\s*(\d+)', role_name, re.IGNORECASE)
                    speaker_suffix = match_speaker.group(1) if match_speaker else "1"
                    evaluator_name = evaluator_map.get((log.Meeting_Number, speaker_suffix))
                    
                    is_waitlist = getattr(log, 'is_waitlist', False)
                    meeting_finished = log.meeting and log.meeting.status == 'finished'
                    
                    status = 'pending'
                    if log.Status == 'Completed' or (not is_waitlist and meeting_finished):
                        status = 'completed'
                        rp_completed = True
                    elif is_waitlist:
                        status = 'waitlist'
                    else:
                        status = 'booked'

                    history_item = {
                        'id': log.id,
                        'name': item_name_with_code,
                        'status': status,
                        'meeting_number': log.Meeting_Number,
                        'meeting_date': log.meeting.Meeting_Date.strftime('%Y-%m-%d') if log.meeting and log.meeting.Meeting_Date else 'N/A',
                        'project_code': display_code,
                        'role_name': role_name.strip(),
                        'project_name': project_name,
                        'speech_title': session_title,
                        'evaluator': evaluator_name,
                        'media_url': log.media.url if log.media else None
                    }
                    
                    speech_data['history_items'].append(history_item)
                    
                    if _status_priority(status) < _status_priority(req_item['status']):
                        req_item['status'] = status
                    
                    used_log_ids.add(log.id)
        
        if not rp_completed:
            all_completed = False
        
        speech_data['requirement_items'].append(req_item)
    
    if all_completed and len(speech_data['requirement_items']) > 0:
            speech_data['status'] = 'completed'
            
    return speech_data, all_completed, has_activity

def _finalize_elective_badges(elective_badges, level_int):
    """Sort electives and add placeholders if needed."""
    level_reqs = get_level_project_requirements().get(level_int, {})
    needed = level_reqs.get('elective_count', 0)
    
    elective_badges.sort(key=lambda x: _status_priority(x['status']))
    
    final_electives = elective_badges[:needed]
    if len(final_electives) < needed:
        for _ in range(needed - len(final_electives)):
            final_electives.append({
                'project_code': f"{level_int}.X",
                'status': 'pending',
                'requirement_items': [{'name': 'Pending Elective', 'status': 'pending'}],
                'history_items': []
            })
    return final_electives


def _collect_extra_roles(logs_for_level, used_log_ids):
    """Collect roles/speeches that were not used for any requirement."""
    extra_roles = []
    
    # Process each entry in the logs
    # logs_for_level is a list of Log Objects OR Dictionaries (grouped roles)
    # We need to handle both
    
    normalized_logs = []
    for entry in logs_for_level:
        if isinstance(entry, dict) and entry.get('log_type') == 'grouped_role':
            normalized_logs.extend(entry['logs'])
        else:
            normalized_logs.append(entry)
            
    for log in normalized_logs:
        if log.id in used_log_ids:
            continue
            
        # Exclude prepared speeches from "extra roles" as requested
        if log.project and log.project.is_prepared_speech:
            continue

        # Check if it's a role or completed
        # Simplify status check
        is_completed = (log.Status == 'Completed')
        is_role = (hasattr(log, 'log_type') and log.log_type == 'role')
        
        if is_completed or is_role:
             # Descriptive logic
            has_real_project = log.Project_ID and log.Project_ID != ProjectID.GENERIC
            project_name = log.project.Project_Name if log.project else None
            session_title = log.Session_Title
            
            if project_name and session_title:
                item_name = f"{project_name} ({session_title})"
            elif project_name:
                item_name = project_name
            elif session_title:
                item_name = session_title
            else:
                item_name = log.session_type.Title if log.session_type else "Activity"
            
            display_code = log.project_code if hasattr(log, 'project_code') else None
            if display_code:
                match = re.match(r"^[A-Z]+\d+$", display_code)
                if match and not has_real_project:
                    display_code = None
            
            item_name_with_code = f"{display_code} {item_name}" if display_code else item_name
            
            role_display = (log.session_type.role.name if log.session_type and log.session_type.role 
                            else (log.session_type.Title if log.session_type else "Activity")).strip()

            is_waitlist = getattr(log, 'is_waitlist', False)
            meeting_finished = log.meeting and log.meeting.status == 'finished'
            status = 'pending'
            if log.Status == 'Completed' or (not is_waitlist and meeting_finished):
                status = 'completed'
            elif is_waitlist:
                status = 'waitlist'
            else:
                status = 'booked'

            extra_roles.append({
                'id': log.id,
                'name': item_name_with_code,
                'status': status,
                'meeting_number': log.Meeting_Number,
                'meeting_date': log.meeting.Meeting_Date.strftime('%Y-%m-%d') if log.meeting and log.meeting.Meeting_Date else 'N/A',
                'project_code': display_code,
                'role_name': role_display
            })
            
    return extra_roles


def _calculate_completion_summary(grouped_logs, pp_mapping, selected_pathway_name=None):
    """
    Calculate completion summary against LevelRole requirements.
    Uses normalize_role_name and get_role_aliases from utils.
    Groups by (level, band) to handle elective pools.
    """
    # Use no_autoflush to prevent warnings about objects not in session during query and property access
    with db.session.no_autoflush:
        level_requirements = LevelRole.query.order_by(LevelRole.level, LevelRole.band, LevelRole.type.desc()).all()
        completion_summary = {}
        used_log_ids = set()
        role_aliases = get_role_aliases()
        
        # Helper for status priority
        def status_priority(s):
            return {'completed': 0, 'booked': 1, 'waitlist': 2, 'pending': 3}.get(s, 4)

        # Group requirements by (level, band)
        reqs_by_band = {}
        for lr in level_requirements:
            # Skip magic 'Elective Pool' record as we now use banding
            if lr.role.strip().lower() == 'elective pool':
                continue
                
            key = (lr.level, lr.band if lr.band is not None else 0)
            if key not in reqs_by_band:
                reqs_by_band[key] = []
            reqs_by_band[key].append(lr)

        # 0. Fetch Required Speeches for the pathway if provided
        speeches_by_level = {}
        pathway_obj = None
        if selected_pathway_name and selected_pathway_name != 'all':
            pathway_obj = Pathway.query.filter_by(name=selected_pathway_name).first()
            if pathway_obj:
                req_speeches = PathwayProject.query.filter_by(
                    path_id=pathway_obj.id,
                    type='required'
                ).order_by(PathwayProject.level, PathwayProject.code).all()
                
                for rs in req_speeches:
                    lvl = rs.level or 0
                    if lvl not in speeches_by_level:
                        speeches_by_level[lvl] = []
                    speeches_by_level[lvl].append(rs)

        # Initialize summary structure
        all_levels = sorted(list(set(lr.level for lr in level_requirements)))
        for lvl in all_levels:
            level_str = str(lvl)
            completion_summary[level_str] = {
                'required': [], 
                'elective': [], 
                'required_completed': True, 
                'elective_completed': True, # Default to True, will set to False if any pool/role not met
                'required_count': 0,
                'required_total': 0,
                'elective_count': 0,
                'elective_required': 0, # Total elective points needed for the level
                'speeches': []
            }

        # Process Each Band
        sorted_keys = sorted(reqs_by_band.keys())
        for lvl, band in sorted_keys:
            level_str = str(lvl)
            band_reqs = reqs_by_band[(lvl, band)]
            logs_for_level = grouped_logs.get(level_str, [])
            
            _process_band_requirements(
                level_str, 
                band_reqs, 
                logs_for_level, 
                used_log_ids, 
                pp_mapping, 
                role_aliases, 
                completion_summary[level_str]
            )
            
        # NEW Part: Unified logic for speech badges (Required and Elective)
        for lvl_str, summary in completion_summary.items():
            lvl_int = int(lvl_str)
            path_id = pathway_obj.id if pathway_obj else None
            
            # 1. Group PathwayProjects into "Badge Groups"
            badge_groups = _get_project_groups_for_level(lvl_int, path_id)

            # 2. Process each badge group
            logs_for_level = grouped_logs.get(lvl_str, [])
            evaluator_map = _build_evaluator_map(logs_for_level)

            # Containers for results
            required_badges = []
            elective_badges = []
            
            for major_code, p_type, rps in badge_groups:
                speech_data, all_completed, has_activity = _process_badge_group(
                    major_code, p_type, rps, logs_for_level, evaluator_map, used_log_ids
                )
                
                if p_type == 'required':
                    required_badges.append(speech_data)
                elif has_activity:
                    elective_badges.append(speech_data)
            
            # 3. Handle Elective Counts and Placeholders
            final_electives = _finalize_elective_badges(elective_badges, lvl_int)
            
            summary['speeches'] = required_badges + final_electives
            summary['speeches'].sort(key=lambda x: x.get('project_code') or '')
            
        # Final pass: Collect Extra Roles (those not used for any requirement)
        for lvl, logs in grouped_logs.items():
            level_str = str(lvl)
            if level_str not in completion_summary:
                continue
            
            extra_roles = []
            for entry in logs:
                items = entry['logs'] if isinstance(entry, dict) and entry.get('log_type') == 'grouped_role' else [entry]
                for log in items:
                    if log.id not in used_log_ids:
                        # Exclude prepared speeches from "extra roles" as requested
                        # They are either in the Speeches column or shouldn't be in roles list
                        if log.project and log.project.is_prepared_speech:
                            continue

                        # check if it's a role or completed
                        if log.Status == 'Completed' or (hasattr(log, 'log_type') and log.log_type == 'role'):
                            # Descriptive logic for project and session
                            has_real_project = log.Project_ID and log.Project_ID != ProjectID.GENERIC
                            project_name = log.project.Project_Name if log.project else None
                            session_title = log.Session_Title
                            
                            if project_name and session_title:
                                item_name = f"{project_name} ({session_title})"
                            elif project_name:
                                item_name = project_name
                            elif session_title:
                                item_name = session_title
                            else:
                                item_name = log.session_type.Title if log.session_type else "Activity"
                            
                            display_code = log.project_code if hasattr(log, 'project_code') else None
                            if display_code:
                                match = re.match(r"^[A-Z]+\d+$", display_code)
                                if match and not has_real_project:
                                    display_code = None
                            
                            item_name_with_code = f"{display_code} {item_name}" if display_code else item_name
                            
                            is_waitlist = getattr(log, 'is_waitlist', False)
                            meeting_finished = log.meeting and log.meeting.status == 'finished'
                            status = 'pending'
                            if log.Status == 'Completed' or (not is_waitlist and meeting_finished):
                                status = 'completed'
                            elif is_waitlist:
                                status = 'waitlist'
                            else:
                                status = 'booked'

                            extra_roles.append({
                                'id': log.id,
                                'name': item_name_with_code,
                                'status': status,
                                'meeting_number': log.Meeting_Number,
                                'meeting_date': log.meeting.Meeting_Date.strftime('%Y-%m-%d') if log.meeting and log.meeting.Meeting_Date else 'N/A',
                                'project_code': display_code,
                                'role_name': (log.session_type.role.name if log.session_type and log.session_type.role else (log.session_type.Title if log.session_type else "Activity")).strip()
                            })
            completion_summary[level_str]['extra_roles'] = extra_roles
            
        # Final cleanup: if elective_required is 0, elective_completed should be True
        for level_str in completion_summary:
            if completion_summary[level_str]['elective_required'] == 0:
                completion_summary[level_str]['elective_completed'] = True

        return completion_summary


def _get_speaker_user(viewed_contact, is_member_view):
    """Get the User object for the speaker."""
    if viewed_contact:
        return viewed_contact.user
    elif is_member_view:
        return current_user
    return None


def _get_pathway_project_mapping(speaker_user, selected_pathway=None):
    """Get mapping of project IDs to types (required/elective)."""
    from .club_context import get_current_club_id
    
    path_name = selected_pathway
    if not path_name and speaker_user:
        club_id = get_current_club_id()
        contact = speaker_user.get_contact(club_id)
        if contact and contact.Current_Path:
            path_name = contact.Current_Path
            
    if not path_name:
        return {}
    
    pathway_obj = Pathway.query.filter_by(name=path_name).first()
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
    achievement_dates = {}
    target_path_name = selected_pathway
    
    if not target_path_name and speaker_user:
        from .club_context import get_current_club_id
        club_id = get_current_club_id()
        contact = speaker_user.get_contact(club_id)
        if contact and contact.Current_Path:
            target_path_name = contact.Current_Path
    
    if speaker_id and speaker_id != -1 and target_path_name:
        try:
            contact = db.session.get(Contact, int(speaker_id))
            if contact:
                completed_levels = contact.get_completed_levels(target_path_name)
                achievement_dates = contact.get_level_achievement_dates(target_path_name)
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
    
    return completed_levels, active_level, achievement_dates


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
        'meeting_id': None,
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
    _attach_owners(all_logs)
    
    project_ids = [log.Project_ID for log in all_logs if log.Project_ID]
    pathway_cache = build_pathway_project_cache(project_ids=project_ids)
    
    grouped_logs = _process_logs(all_logs, filters, pathway_cache)
    sorted_grouped_logs = _sort_and_consolidate(grouped_logs)
    
    speaker_user = contact.user
    pp_mapping = _get_pathway_project_mapping(speaker_user)
    
    completion_summary = _calculate_completion_summary(grouped_logs, pp_mapping)
    
    summary = completion_summary.get(str(level))
    
    return render_template('partials/_level_progress.html', summary=summary)






# ============================================================================
# MAIN ROUTE
# ============================================================================

@speech_logs_bp.route('/speech_logs', methods=['GET'])
@login_required
@authorized_club_required
def show_speech_logs():
    """Shows all speech logs, or only the member's logs depending on permissions & view_mode."""
    # 1. Get view settings and filters
    can_view_all, view_mode, is_member_view = _get_view_settings()
    filters = _parse_filters(is_member_view, can_view_all)
    
    # 2. Get viewed contact
    viewed_contact = _get_viewed_contact(filters['speaker_id'])

    # 3. Get pathway information
    pathway_info = _get_pathway_info(viewed_contact, request.args.get('pathway'), filters)
    filters['pathway'] = pathway_info['selected_pathway']
    
    # NEW: Get meetings for the filter (allow past meetings)
    upcoming_meetings, default_meeting_id = get_meetings_by_status(
        limit_past=None, columns=[Meeting.id, Meeting.Meeting_Date, Meeting.status, Meeting.Meeting_Number], only_with_logs=False)
    
    selected_meeting_id = filters.get('meeting_id')
    
    # Only force a default meeting selection in Admin/Meeting View
    if view_mode == 'admin':
        if not selected_meeting_id:
            selected_meeting_id = default_meeting_id or (
                upcoming_meetings[0][0] if upcoming_meetings else None)
            filters['meeting_id'] = selected_meeting_id
            
    # Find meeting number for display title
    selected_meeting_number = 'N/A'
    if selected_meeting_id:
        # Check in upcoming_meetings first
        for m in upcoming_meetings:
            if str(m[0]) == str(selected_meeting_id):
                selected_meeting_number = m[3] # Meeting_Number is at index 3
                break
        
        # If not found (maybe filtered), we could fetch it from DB, but usually it's in the list
        if selected_meeting_number == 'N/A' and upcoming_meetings:
             # Just in case, fall back to DB or keep N/A
             pass
    
    # 4. Get dropdown metadata (using utils)
    dropdown_data = get_dropdown_metadata()
    
    # 5. Fetch logs
    if view_mode == 'search':
        from .club_context import get_current_club_id
        club_id = get_current_club_id()
        all_logs = _search_logs(request.args.get('q', ''), can_view_all, club_id)
    else:
        all_logs = _fetch_logs_with_filters(filters)
    _attach_owners(all_logs)
    
    # 6. Build pathway cache for performance
    project_ids = [log.Project_ID for log in all_logs if log.Project_ID]
    pathway_cache = build_pathway_project_cache(project_ids=project_ids)
    
    # 7. Process logs
    grouped_logs = _process_logs(all_logs, filters, pathway_cache, view_mode=view_mode)
    sorted_grouped_logs = _sort_and_consolidate(grouped_logs)
    
    # 7.1 Filter for display in Member View: Only show logs linked to non-generic projects
    if is_member_view and view_mode != 'search':
        filtered_logs = {}
        for group, logs in sorted_grouped_logs.items():
            group_filtered = []
            for log in logs:
                # Get Project_ID from SessionLog object or dictionary
                pid = getattr(log, 'Project_ID', None)
                if pid is None and isinstance(log, dict):
                    pid = log.get('Project_ID')
                
                # Only include if it has a real project linked
                if pid and pid != ProjectID.GENERIC:
                    group_filtered.append(log)
            
            if group_filtered:
                filtered_logs[group] = group_filtered
        sorted_grouped_logs = filtered_logs
    
    # 8. Calculate completion summary
    speaker_user = _get_speaker_user(viewed_contact, is_member_view)
    pp_mapping = _get_pathway_project_mapping(speaker_user, filters['pathway'])
    completion_summary = _calculate_completion_summary(grouped_logs, pp_mapping, selected_pathway_name=filters['pathway'])
    
    # 9. Get achievement status
    completed_levels, active_level, achievement_dates = _get_achievement_status(
        filters['speaker_id'], speaker_user, filters['pathway']
    )
    
    # 10. Get role metadata
    role_icons = _get_role_metadata()
    
    
    # 11. Get path progress data if in member view
    progress_data_rows = None
    if is_member_view:
        progress_data_rows = _get_path_progress_data(completion_summary)

    # NEW: Fetch data for Planner Modal (Unpublished Meetings & User Projects)
    # Only needed for member view or if we want the button available generally
    planner_meetings = []
    planner_projects = []
    
    if is_member_view:
        # Fetch unpublished meetings
        from .club_context import get_current_club_id
        club_id = get_current_club_id()
        planner_meetings = Meeting.query.filter_by(club_id=club_id, status='unpublished').order_by(Meeting.Meeting_Number).all()
        
        # Fetch projects grouped by level
        contact = current_user.get_contact(club_id)
        projects_by_level = {}
        if contact:
            projects = contact.get_pathway_projects_with_status()
            for p in projects:
                level = p.level or 1
                if level not in projects_by_level:
                    projects_by_level[level] = []
                projects_by_level[level].append(p)
                
        sorted_levels = sorted(projects_by_level.keys())
        planner_projects = [(level, projects_by_level[level]) for level in sorted_levels]

    # 12. Render template
    if view_mode == 'search':
        template_name = 'search_view.html'
    else:
        template_name = 'member_view.html'
    return render_template(
        template_name,
        meetings=planner_meetings,            # For Planner Modal
        grouped_projects=planner_projects,    # For Planner Modal
        grouped_logs=sorted_grouped_logs,

        roles=dropdown_data['roles'],
        role_icons=role_icons,
        pathways=dropdown_data['pathways'],
        levels=range(1, 6),
        completed_levels=completed_levels,
        achievement_dates=achievement_dates,
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
        ProjectID=ProjectID,
        upcoming_meetings=upcoming_meetings,
        selected_meeting_id=selected_meeting_id,
        selected_meeting_number=selected_meeting_number,
        progress_data_rows=progress_data_rows
    )


@speech_logs_bp.route('/speech_logs/projects')
@login_required
def show_project_view():
    """
    Display speech logs in a project-centric view (bar chart style).
    Accessible to admins mainly, but logic could allow others.
    """
    if not is_authorized(Permissions.SPEECH_LOGS_MANAGE):
        from flask import redirect, url_for
        return redirect(url_for('speech_logs_bp.show_speech_logs', view_mode='member')) 
             
    from .utils import get_terms, get_active_term, get_date_ranges_for_terms
             
    terms = get_terms()
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
    
    # Multi-select support for terms
    selected_term_ids = request.args.getlist('term')
    
    current_term = get_active_term(terms)
    
    if not selected_term_ids:
        # Default to current term if available, else first one
        if current_term:
            selected_term_ids = [current_term['id']]
        elif terms:
            selected_term_ids = [terms[0]['id']]
            
    # Calculate date ranges for all selected terms
    date_ranges = get_date_ranges_for_terms(selected_term_ids, terms)
    should_filter_date = bool(selected_term_ids)
    
    selected_pathway_id = request.args.get('pathway')
    
    from .club_context import get_current_club_id
    current_club_id = get_current_club_id()
    
    # Query Data: Count sessions per project matching ANY of the date ranges
    # Standard filters
    filters = [
        SessionLog.Project_ID.isnot(None),
        SessionLog.Project_ID != ProjectID.GENERIC,
        Meeting.club_id == current_club_id
    ]
    
    # Date Range Filter (OR condition)
    from sqlalchemy import or_, false
    if date_ranges:
        date_conditions = [Meeting.Meeting_Date.between(start, end) for start, end in date_ranges]
        filters.append(or_(*date_conditions))
    elif should_filter_date:
        # User selected terms but no valid ranges found -> Match Nothing
        filters.append(false())
    
    if selected_pathway_id:
        filters.append(SessionLog.pathway == selected_pathway_id)
        
    query = db.session.query(SessionLog).join(Meeting, SessionLog.meeting_id == Meeting.id).filter(*filters).order_by(Meeting.Meeting_Number.asc()).options(
        joinedload(SessionLog.project),
        joinedload(SessionLog.meeting),
        joinedload(SessionLog.session_type).joinedload(SessionType.role)
    )
    
    logs = query.all()
    
    # Process into Chart Data
    # Structure: { project_id: { 'project': ProjectObj, 'count': int, 'owners': [ContactObj], 'level_counts': dict } }
    project_data_map = {}
    
    # Pre-fetch pathway cache for efficient level determination
    project_ids_for_cache = [log.Project_ID for log in logs if log.Project_ID]
    pathway_cache = build_pathway_project_cache(project_ids=project_ids_for_cache)
    
    # Fetch all owners for these logs in one query to avoid N+1
    # Use helper utility that attempts to attach owners for both types of roles (single vs shared)
    _attach_owners(logs)

    for log in logs:
        if not log.project:
            continue
            
        pid = log.Project_ID
        if pid not in project_data_map:
            project_data_map[pid] = {
                'id': pid,
                'project_name': log.project.Project_Name,
                'count': 0,
                'level_counts': {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 'Other': 0},
                'owners': []
            }
        
        project_data_map[pid]['count'] += 1
        
        # Get owners for this log (now attached by _attach_owners)
        log_owners = log.owners
        primary_owner_path = log_owners[0].Current_Path if log_owners else None
        
        # Determine Level for this specific log instance
        # Prefer selected pathway filter, then primary owner's path
        context_path = selected_pathway_id or primary_owner_path
        display_level, _, _ = log.get_display_level_and_type(pathway_cache, context_pathway_name=context_path)
        
        # Aggregation by Level
        level_key = display_level
        try:
            level_key = int(display_level)
            if level_key not in [1, 2, 3, 4, 5]:
                level_key = 'Other'
        except (ValueError, TypeError):
             level_key = 'Other'
             
        project_data_map[pid]['level_counts'][level_key] += 1
        
        if log_owners:
            # Append all owners
            project_data_map[pid]['owners'].extend(log_owners)
            
    # Deduplicate owners list for display & Convert to list
    chart_data = []
    
    for pid in project_data_map:
        # Use set to dedup by ID, then sort by Name
        unique_owners = {c.id: c for c in project_data_map[pid]['owners']}.values()
        project_data_map[pid]['owners'] = sorted(list(unique_owners), key=lambda x: x.Name)
        chart_data.append(project_data_map[pid])

    # Sort by count desc
    chart_data.sort(key=lambda x: x['count'], reverse=True)
    
    # Find global max for scaling
    current_max_count = 0
    if chart_data:
        current_max_count = max(item['count'] for item in chart_data)

    return render_template(
        'project_view.html',
        terms=terms,
        current_term=current_term, # Kept for backward compat or display title
        selected_term_ids=selected_term_ids, # Pass selected IDs list
        chart_data=chart_data,
        max_count=current_max_count,
        active_pathways=active_pathways,
        inactive_pathways=inactive_pathways,
        selected_pathway=selected_pathway_id,
        can_view_all=True
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

    from .club_context import get_current_club_id
    club_id = get_current_club_id()
    contact = current_user.get_contact(club_id) if current_user.is_authenticated else None
    current_user_contact_id = contact.id if contact else None

    if not is_authorized(Permissions.SPEECH_LOGS_MANAGE):
        current_owners = [o.id for o in log.owners]
        if current_user_contact_id not in current_owners:
            return jsonify(success=False, message="Permission denied. You can only view details for your own speech logs."), 403


    # Retrieve correct credential context
    # The modal edits the log's owner data, so we should look up the
    # primary owner's credential — not the current admin user's.
    # Only use current user's contact_id if they are one of the owners.
    target_contact_id = None
    if log.owners:
        owner_ids = [o.id for o in log.owners]
        if current_user_contact_id in owner_ids:
            # Current user is an owner — use their credential
            target_contact_id = current_user_contact_id
        else:
            # Admin editing someone else's log — use primary owner
            target_contact_id = owner_ids[0]
            
    credential_value = ""
    target_pathway = ""
    target_level = ""
    owner_name = ""
    
    if log.owners and target_contact_id:
        target_contact = next((c for c in log.owners if c.id == target_contact_id), None)
        if target_contact:
            owner_name = target_contact.Name

        # Find the specific OwnerMeetingRoles entry
        # Logic matches Session.owners property but specific to one contact
        
        # Determine role_id and meeting_id
        session_type = log.session_type
        role_obj = session_type.role if session_type else None
        role_id = role_obj.id if role_obj else 0
        meeting_id = log.meeting.id if log.meeting else None
        
        if meeting_id:
             omr_query = OwnerMeetingRoles.query.filter_by(
                 meeting_id=meeting_id,
                 role_id=role_id,
                 contact_id=target_contact_id
             )
             
             # For single-owner roles, prefer the OMR linked to this specific log
             # For shared roles (or legacy records), just match by meeting+role+contact
             has_single_owner = role_obj.has_single_owner if role_obj else True
             
             if has_single_owner:
                 # Try exact match first, then fall back to any match
                 omr = omr_query.filter_by(session_log_id=log.id).first()
                 if not omr:
                     omr = omr_query.first()
             else:
                 omr = omr_query.first()
             if omr:
                 if omr.credential:
                     credential_value = omr.credential
                 target_pathway = omr.target_pathway if omr.target_pathway is not None else "Non Pathway"
                 target_level = omr.target_level or ""

    # Use the helper function to get project code
    project_code = ""
    # Priority: target_pathway (from OwnerMeetingRoles) > log.pathway > "Non Pathway"
    # For functional roles (Timer, GE, etc.) where target_pathway is NULL and log.pathway is also NULL,
    # we should NOT fall back to owner's Current_Path - they should show "Non Pathway" directly.
    # Only speeches (Prepared Speech, Pathway Speech, Presentation) should use owner's Current_Path as fallback.
    pathway_name_to_return = target_pathway if target_pathway else log.pathway
    if not pathway_name_to_return:
        # Only use owner's Current_Path as fallback if log.pathway exists (speech case)
        # For functional roles with no target_pathway and no log.pathway, show "Non Pathway"
        if log.pathway and log.owner and log.owner.Current_Path:
            pathway_name_to_return = log.owner.Current_Path
    if not pathway_name_to_return:
        pathway_name_to_return = "Non Pathway"
    level = target_level if target_level else 1
    
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
            is_guest_without_user = (log.owner.Type == 'Guest') or (log.owner.user is None)
            if not is_guest_without_user and log.owner.Current_Path:
                pathway_name_to_return = log.owner.Current_Path
            else:
                pathway_name_to_return = "Non Pathway"

        # 2. Derive level and project code based on that pathway
        level = log.project.get_level(pathway_name_to_return)
        
        if not getattr(log, 'project_code', None):
            log.project_code = log.project.get_code(pathway_name_to_return)

    from .utils import derive_credentials

    owner_ids = [o.id for o in log.owners]
    owner_targets = {}
    owners_data = []

    session_type = log.session_type
    role_obj = session_type.role if session_type else None
    role_id = role_obj.id if role_obj else 0
    meeting_id = log.meeting.id if log.meeting else None
    role_name = role_obj.name if role_obj else (session_type.Title if session_type else "N/A")

    for o in log.owners:
        omr = None
        if meeting_id and role_id:
            omr_query = OwnerMeetingRoles.query.filter_by(
                meeting_id=meeting_id,
                role_id=role_id,
                contact_id=o.id
            )
            has_single_owner = role_obj.has_single_owner if role_obj else True
            if has_single_owner:
                omr = omr_query.filter_by(session_log_id=log.id).first()
                if not omr:
                    omr = omr_query.first()
            else:
                omr = omr_query.first()

        t_pathway = None
        t_level = None
        if omr:
            t_pathway = omr.target_pathway if omr.target_pathway is not None else "Non Pathway"
            t_level = omr.target_level or ""

        owner_targets[str(o.id)] = {
            "pathway": t_pathway,
            "level": t_level
        }

        owners_data.append({
            "id": o.id,
            "Name": o.Name,
            "DTM": o.DTM,
            "Type": o.Type,
            "Credentials": derive_credentials(o),
            "Current_Path": o.Current_Path,
            "registered_paths": [p['name'] for p in o.get_member_pathways()]
        })

    log_data = {
        "id": log.id,
        "Session_Title": log.Session_Title,
        "Project_ID": log.Project_ID,
        "pathway": pathway_name_to_return,
        "level": level,
        "project_code": log.project_code,
        "credential": credential_value,
        "owner_name": owner_name,
        "owner_id": target_contact_id,
        "registered_paths": [p['name'] for p in target_contact.get_member_pathways()] if (log.owners and target_contact_id and target_contact) else [],
        "target_pathway": target_pathway,
        "target_level": target_level,
        "Media_URL": log.media.url if (is_authorized(Permissions.MEDIA_MANAGE) and log.media) else "",
        "session_type_title": log.session_type.Title if log.session_type else "Pathway Speech",
        "owner_ids": owner_ids,
        "owner_targets": owner_targets,
        "role": role_name,
        "owners_data": owners_data
    }

    return jsonify(success=True, log=log_data)


@speech_logs_bp.route('/speech_log/update/<int:log_id>', methods=['POST'])
@login_required
def update_speech_log(log_id):
    """
    Updates a speech log with new data from the edit modal.
    """
    log = SessionLog.query.options(
        joinedload(SessionLog.meeting),
        joinedload(SessionLog.session_type),
        joinedload(SessionLog.project)
    ).get_or_404(log_id)

    # Permission Checks
    from .club_context import get_current_club_id
    club_id = get_current_club_id()
    contact = current_user.get_contact(club_id) if current_user.is_authenticated else None
    current_user_contact_id = contact.id if contact else None
    
    if not is_authorized(Permissions.SPEECH_LOGS_MANAGE):
        # Check if user is ONE OF the owners
        current_owners = [o.id for o in log.owners]
        is_owner = (current_user_contact_id in current_owners)
        if not (is_authorized(Permissions.MEMBERS_SELF) and is_owner):
            return jsonify(success=False, message="Permission denied. You can only edit your own speech logs."), 403

    data = request.get_json()
    media_url = data.get('media_url') or None
    project_id = data.get('project_id')
    credential_val = data.get('credential')
    
    # 1. Update Owner Logic: Handle list of owners FIRST so target updates apply to them
    from .services.role_service import RoleService
    owner_ids = data.get('owner_ids', []) # Expected list of IDs
    
    # Backward compatibility: if single 'owner_id' provided and no 'owner_ids', use it
    if not owner_ids and 'owner_id' in data:
         val = data.get('owner_id')
         if val:
             owner_ids = [int(val)]

    if 'owner_ids' in data or 'owner_id' in data:
        RoleService.assign_meeting_role(log, owner_ids, is_admin=is_authorized(Permissions.SPEECH_LOGS_MANAGE))
        # Flush changes and refresh log to ensure we have the latest owners
        db.session.flush()
        db.session.refresh(log)
    
    # Update Credential in OwnerMeetingRoles
    # We update for ALL current owners assigned to this log
    if credential_val is not None:
         
         session_type = log.session_type
         role_obj = session_type.role if session_type else None
         has_single_owner = role_obj.has_single_owner if role_obj else True
         
         # Identify owners to update
         target_owner_ids = [o.id for o in log.owners]
         
         if target_owner_ids:
              meeting_id = log.meeting_id
              if meeting_id:
                 role_id = role_obj.id if role_obj else 0
                 query = OwnerMeetingRoles.query.filter(
                     OwnerMeetingRoles.meeting_id == meeting_id,
                     OwnerMeetingRoles.role_id == role_id,
                     OwnerMeetingRoles.contact_id.in_(target_owner_ids)
                 )
                 
                 omr_entries = query.all()
                 for omr in omr_entries:
                     omr.credential = credential_val
         
    # Update target_pathway and target_level in OwnerMeetingRoles
    pathway_val = data.get('pathway')
    level_val = data.get('level')
    owner_targets = data.get('owner_targets') or {}
    
    session_type = log.session_type
    role_obj = session_type.role if session_type else None
    has_single_owner = role_obj.has_single_owner if role_obj else True
    target_owner_ids = [o.id for o in log.owners]
    
    affected_log_ids = []
    if target_owner_ids and log.meeting_id:
        role_id = role_obj.id if role_obj else 0
        query = OwnerMeetingRoles.query.filter(
            OwnerMeetingRoles.meeting_id == log.meeting_id,
            OwnerMeetingRoles.role_id == role_id,
            OwnerMeetingRoles.contact_id.in_(target_owner_ids)
        )
            
        for omr in query.all():
            if omr.session_log_id and omr.session_log_id != log.id:
                affected_log_ids.append(omr.session_log_id)
                
            contact_str = str(omr.contact_id)
            if contact_str in owner_targets:
                target = owner_targets[contact_str]
                p_val = target.get('pathway')
                l_val = target.get('level')
                if p_val is not None:
                    omr.target_pathway = None if p_val == "Non Pathway" else p_val
                if l_val is not None:
                    if p_val == "Non Pathway" or not omr.target_pathway:
                        omr.target_level = None
                    else:
                        omr.target_level = str(l_val) if l_val else None
            else:
                if pathway_val is not None:
                    omr.target_pathway = None if pathway_val == "Non Pathway" else pathway_val
                if level_val is not None:
                    if pathway_val == "Non Pathway" or not omr.target_pathway:
                        omr.target_level = None
                    else:
                        omr.target_level = str(level_val) if level_val else None

        # For shared roles, find all other session logs with the same role in this meeting
        if not has_single_owner:
            from app.models.session import SessionType
            related_logs = SessionLog.query.join(SessionType).filter(
                SessionLog.meeting_id == log.meeting_id,
                SessionType.role_id == role_id,
                SessionLog.id != log.id
            ).all()
            for rl in related_logs:
                affected_log_ids.append(rl.id)
                # Ensure functional roles have NULL pathway in SessionLog
                rl.update_pathway(None)
         
    # Pre-fetch project if needed for duration logic
    updated_project = None
    if project_id and project_id not in [None, "", "null"]:
        updated_project = db.session.get(Project, project_id)

    # 1. Update Basic Fields
    if 'session_title' in data:
        log.Session_Title = data['session_title'] or (updated_project.Project_Name if updated_project else None)

    # 2. Use Model Methods for Complex logic
    log.update_media(media_url)

    pathway_val = data.get('pathway')
    primary_owner = log.owners[0] if log.owners else None
    
    is_prepared_speech = session_type and session_type.Title == 'Prepared Speech'
    is_project = (session_type and session_type.Valid_for_Project and project_id and project_id != ProjectID.GENERIC) or is_prepared_speech

    if is_project:
        if not pathway_val:
            if primary_owner:
                is_guest_without_user = (primary_owner.Type == 'Guest') or (primary_owner.user is None)
                if not is_guest_without_user and primary_owner.Current_Path:
                    pathway_val = primary_owner.Current_Path
            if not pathway_val:
                pathway_val = "Non Pathway"
            
        if pathway_val:
            log.update_pathway(pathway_val)
    else:
        # For functional roles, the session itself doesn't have a pathway.
        # Credit tracking is fully handled by OwnerMeetingRoles.target_pathway.
        log.update_pathway(None)

    log.update_durations(data, updated_project)
    
    # 3. Derive Project Code
    log.project_code = log.derive_project_code()

    speaker_is_dtm = False
    if session_type and session_type.Title == 'Evaluation' and log.Session_Title:
        from app.models.contact import Contact
        speaker = Contact.query.filter(Contact.Name == log.Session_Title.strip()).first()
        if speaker and speaker.DTM:
            speaker_is_dtm = True

    try:
        db.session.commit()
        
        # 4. Get response data from model
        summary = log.get_summary_data()

        return jsonify(
            success=True,
            session_title=log.Session_Title,
            project_name=summary['project_name'],
            project_code=summary['project_code'],
            pathway=pathway_val if pathway_val else summary['pathway'],
            project_id=log.Project_ID,
            duration_min=log.Duration_Min,
            duration_max=log.Duration_Max,
            media_url=media_url,
            affected_log_ids=affected_log_ids,
            speaker_is_dtm=speaker_is_dtm
        )

    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@speech_logs_bp.route('/speech_log/suspend/<int:log_id>', methods=['POST'])
@login_required
def suspend_speech_log(log_id):
    if not is_authorized(Permissions.SPEECH_LOGS_MANAGE):
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
        
        progress_html = ""
        if log.owners:
             # Calculate for Primary Owner (or we could return map for all?)
             # Frontend expects single HTML. Let's return for primary.
             progress_html = _get_level_progress_html(log.owner.id, display_level)
        
        return jsonify(success=True, level=display_level, progress_html=progress_html)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500




@speech_logs_bp.route('/speech_log/complete/<int:log_id>', methods=['POST'])
@login_required
def complete_speech_log(log_id):
    log = SessionLog.query.get_or_404(log_id)

    current_user_contact_id = current_user.contact_id if current_user.is_authenticated else None

    if not is_authorized(Permissions.SPEECH_LOGS_MANAGE):
        current_owners = [o.id for o in log.owners]
        if current_user_contact_id not in current_owners:
            return jsonify(success=False, message="Permission denied."), 403
        # Also check if meeting is in the past for non-admins
        if log.meeting and log.meeting.Meeting_Date and log.meeting.Meeting_Date >= datetime.today().date():
            return jsonify(success=False, message="You can only complete logs for past meetings."), 403


    log.Status = 'Completed'

    try:
        db.session.commit()
        
        # Trigger metadata sync (including Next_Project calculation) after commit
        for owner in log.owners:
            from .utils import sync_contact_metadata
            sync_contact_metadata(owner.id)
            
        # Calculate new progress HTML
        display_level = 1
        pathway_cache = build_pathway_project_cache(project_ids=[log.Project_ID]) if log.Project_ID else {}
        display_level, _, _ = log.get_display_level_and_type(pathway_cache)
        
        progress_html = ""
        if log.owners:
            progress_html = _get_level_progress_html(log.owner.id, display_level)
            
        return jsonify(success=True, level=display_level, progress_html=progress_html)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500
