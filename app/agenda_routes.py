# vpemaster/agenda_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, send_file, current_app, flash
from flask_login import current_user
from .auth.utils import login_required, is_authorized, club_permission_required
from .auth.permissions import Permissions
from .models import SessionLog, SessionType, Contact, Meeting, Project, Media, Roster, MeetingRole, Vote, Pathway, PathwayProject, OwnerMeetingRoles, Planner, Waitlist, Club, Ticket
from .constants import ProjectID, SPEECH_TYPES_WITH_PROJECT, GLOBAL_CLUB_ID
from .services.export import MeetingExportService
from .services.export.context import MeetingExportContext
from .services.meeting_slide_service import MeetingSlideService
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


def _get_agenda_logs(meeting_id):
    """Fetches all agenda logs and related data for a specific meeting."""
    query = db.session.query(SessionLog)\
        .options(
            orm.joinedload(SessionLog.session_type).joinedload(
                SessionType.role),  # Eager load SessionType and Role
            orm.joinedload(SessionLog.meeting),      # Eager load Meeting
            orm.joinedload(SessionLog.project),      # Eager load Project
            orm.joinedload(SessionLog.project),      # Eager load Project
            # owners is now a property, cannot be joinedloaded
            orm.joinedload(SessionLog.media)
    )

    if meeting_id:
        query = query.filter(SessionLog.meeting_id == meeting_id)

    # Order by sequence
    logs = query.order_by(SessionLog.Meeting_Seq.asc()).all()

    # Batch-pre-fetch owners for all logs in one query to avoid the N+1 in
    # SessionLog.owners. The owners property joins Contact with
    # OwnerMeetingRoles filtered by (meeting_id, role_id, [session_log_id
    # if has_single_owner]). We load all OMRs for the meeting once with
    # the Contact relationship joined, then materialize the per-log owner
    # list and stash it on _cached_owners — which the property checks
    # before re-querying.
    if meeting_id and logs:
        omrs = db.session.query(OwnerMeetingRoles)\
            .options(orm.joinedload(OwnerMeetingRoles.contact))\
            .filter(OwnerMeetingRoles.meeting_id == meeting_id)\
            .all()
        omr_index = {}
        for omr in omrs:
            omr_index.setdefault((omr.session_log_id, omr.role_id), []).append(omr.contact)
        for log in logs:
            if not log.meeting:
                log._cached_owners = []
                continue
            target_role_id = None
            has_single_owner = True
            if log.session_type and log.session_type.role:
                target_role_id = log.session_type.role_id
                has_single_owner = log.session_type.role.has_single_owner
            if has_single_owner:
                log._cached_owners = list(omr_index.get((log.id, target_role_id), []))
            else:
                # Shared role: no session_log_id filter in the original
                # property — match OMRs by role_id across any session_log_id.
                seen = set()
                result = []
                for (sid, rid), contacts in omr_index.items():
                    if rid != target_role_id:
                        continue
                    for c in contacts:
                        if c is not None and c.id not in seen:
                            seen.add(c.id)
                            result.append(c)
                log._cached_owners = result

    # Populate users and primary clubs for all owners (SessionLog.owners is a list)
    all_owners = []
    for log in logs:
        all_owners.extend(log.owners)

    if all_owners:
        from .club_context import get_current_club_id
        Contact.populate_users(all_owners, get_current_club_id())
        Contact.populate_primary_clubs(all_owners)
    return logs


def _get_project_speakers(meeting_id):
    """Gets a list of speakers for a given meeting."""
    if not meeting_id:
        return []
        
    from .models import OwnerMeetingRoles
    speaker_logs = db.session.query(Contact.Name)\
        .join(OwnerMeetingRoles, Contact.id == OwnerMeetingRoles.contact_id)\
        .join(SessionType, OwnerMeetingRoles.role_id == SessionType.role_id)\
        .join(Meeting, OwnerMeetingRoles.meeting_id == Meeting.id)\
        .filter(
            Meeting.id == meeting_id,
            SessionType.Valid_for_Project == True
    ).distinct().all()
    return [name[0] for name in speaker_logs]


def safe_int(val):
    """Safely converts a value to int, handling None, 'null', '', and invalid strings."""
    if val in [None, "", "null", "None"]:
        return None
    try:
        return int(float(val)) # Handle "5.0" strings just in case
    except (ValueError, TypeError):
        return None

def _create_or_update_session(item, meeting_id, seq, updated_role_groups=None):
    meeting = Meeting.query.get(meeting_id)
    if not meeting:
        # This shouldn't happen if we only use IDs, but we can have it for robustness
        return

    type_id = safe_int(item.get('type_id'))
    session_type = db.session.get(SessionType, type_id) if type_id else None

    # --- Owner ID Handling ---
    # Enhanced to support owner_ids list
    owner_ids = item.get('owner_ids', [])
    owner_id = safe_int(item.get('owner_id'))
    
    # Backward compatibility: if owner_id present but owner_ids empty, use owner_id
    if owner_id and not owner_ids:
        # Filter out '0' if that was used as a placeholder
        if owner_id != 0:
            owner_ids = [owner_id]
            
    # Filter 0s and Nones from list
    from flask import current_app
    current_app.logger.info(f"LOG sync: received owner_ids={owner_ids}, owner_id={owner_id} for item {item.get('id')}")
    owner_ids = [safe_int(oid) for oid in owner_ids if safe_int(oid) and safe_int(oid) != 0]
    current_app.logger.info(f"LOG sync: after conversion owner_ids={owner_ids}")

    # Fetch contacts
    owner_contacts = []
    if owner_ids:
        owner_contacts = db.session.query(Contact).filter(Contact.id.in_(owner_ids)).all()
        # Sort to preserve order of input if important, using dictionary
        contacts_map = {c.id: c for c in owner_contacts}
        owner_contacts = [contacts_map[oid] for oid in owner_ids if oid in contacts_map]
    current_app.logger.info(f"LOG sync: fetched {len(owner_contacts)} contacts for owner_ids={owner_ids}")

    # Primary owner for legacy fields
    owner_contact = owner_contacts[0] if owner_contacts else None
    owner_id = owner_contact.id if owner_contact else None

    # --- Project ID and Status ---
    project_id = safe_int(item.get('project_id'))
    
    status = item.get('status') if item.get('status') else 'Booked'
    session_title = item.get('session_title')
    
    from flask import current_app
    current_app.logger.info(f"Processing session item: id={item.get('id')}, title='{session_title}'")
    
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

    # Read pathway early so project_code derivation uses the user's selected pathway
    early_pathway_val = item.get('pathway') or None

    if item.get('id') == 'new':
        log_for_derivation = SessionLog(
            Project_ID=project_id,
            Type_ID=type_id,
            # owners are now managed via OwnerMeetingRoles, not set directly
            session_type=session_type,
            project=db.session.get(Project, project_id) if project_id else None
        )
        # Note: owners is a read-only property; derive_project_code accepts owner_contact directly
    else:
        log_for_derivation = db.session.get(SessionLog, item['id'])
        # Temporarily update for derivation
        log_for_derivation.Project_ID = project_id
        log_for_derivation.Type_ID = type_id
        # Note: owners is a read-only property; derive_project_code accepts owner_contact directly
        log_for_derivation.session_type = session_type

    project_code = log_for_derivation.derive_project_code(owner_contact, pathway_override=early_pathway_val)
        
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
    # Unified rule: save whatever the frontend sends. If nothing sent,
    # default to owner's Current_Path (for members) or "Non Pathway" (for guests/no path).
    pathway_val = item.get('pathway')
    if not pathway_val:
        if owner_contact:
            is_guest = (owner_contact.Type == 'Guest') or (owner_contact.user is None)
            if not is_guest and owner_contact.Current_Path:
                pathway_val = owner_contact.Current_Path
            else:
                pathway_val = 'Non Pathway'
        else:
            pathway_val = 'Non Pathway'
        
    log = None
    old_owner_id = None
    old_role = None

    # --- Create or Update SessionLog ---
    # Create valid log object first (owners will be assigned via RoleService.assign_meeting_role)
    if item['id'] == 'new':
        new_log = SessionLog(
            meeting_id=meeting.id,
            Meeting_Seq=seq,
            Type_ID=type_id,
            # owners is a read-only property - do not set here
            Duration_Min=duration_min,
            Duration_Max=duration_max,
            Project_ID=project_id,
            Session_Title=session_title,
            Status=status,
            project_code=project_code,
            pathway=pathway_val,
            hidden=item.get('is_hidden', session_type.Is_Hidden if session_type else False)
        )
        db.session.add(new_log)
        # Flush to get the log.id before calling RoleService
        db.session.flush()
        # Refresh to load relationships (session_type, meeting) needed by RoleService
        db.session.refresh(new_log)
        log = new_log
        old_owner_id = None
        old_role = None
    else:
        log = db.session.get(SessionLog, item['id'])
        if log:
            # Capture old state for roster sync
            old_owner_id = log.owner.id if (log.owners and log.owner) else None
            old_role = log.session_type.role if log.session_type and log.session_type.role else None
            
            log.meeting_id = meeting.id
            log.Meeting_Seq = seq
            # log.Type_ID = type_id # Defer update to handle role changes
            
            log.Duration_Min = duration_min
            log.Duration_Max = duration_max
            log.Project_ID = project_id
            log.Status = status
            if session_title is not None:
                current_app.logger.info(f"LOG {log.id}: Updating Session_Title to '{session_title}'")
                log.Session_Title = session_title
            
            if 'is_hidden' in item:
                log.hidden = item['is_hidden']
            
            # Use log.update_pathway for consistent sync logic
            is_prepared_speech = session_type and session_type.Title == 'Prepared Speech'
            is_project = (session_type and session_type.Valid_for_Project and project_id and project_id != ProjectID.GENERIC) or is_prepared_speech

            if is_project:
                if pathway_val:
                    log.update_pathway(pathway_val)
            else:
                log.update_pathway(None)

    # Use shared assignment logic if owner changed or it's a new log with an owner
    # For multi-owner, we check if the set of owners changed
    if log:
        new_role = session_type.role if session_type else None
        
        # Track role group to avoid redundant updates for shared roles
        # Only apply to shared roles (has_single_owner=False)
        role_group_key = None
        if new_role and not new_role.has_single_owner:
            role_group_key = f"{meeting.id}_{new_role.id}"

        # Compare sets of IDs
        old_owner_ids_set = set(c.id for c in (log.owners or []))
        new_owner_ids_set = set(owner.id for owner in owner_contacts)
        
        role_changed = (old_role != new_role)
        owner_changed = (old_owner_ids_set != new_owner_ids_set)
        
        from flask import current_app
        current_app.logger.info(f"LOG {log.id}: role={old_role.name if old_role else 'None'} -> {new_role.name if new_role else 'None'} (changed={role_changed})")
        current_app.logger.info(f"LOG {log.id}: owners={old_owner_ids_set} -> {new_owner_ids_set} (changed={owner_changed})")
        
        # Skip assignment if this shared role group was already updated in this transaction
        if role_group_key and updated_role_groups is not None and role_group_key in updated_role_groups:
             current_app.logger.info(f"LOG {log.id}: Shared role {new_role.name} already updated in this request. Skipping assignment.")
        elif role_changed or owner_changed:
            # Force unassign from the OLD role if the type changed
            Roster.sync_role_assignment(log.meeting_id, old_owner_id, old_role, 'unassign')
            
            # Call Service with LIST of IDs
            current_app.logger.info(f"LOG {log.id}: Calling RoleService.assign_meeting_role with owner_ids={[c.id for c in owner_contacts]}")
            RoleService.assign_meeting_role(log, [c.id for c in owner_contacts], is_admin=True)
            
            # Flush to ensure queries reflect these changes for subsequent logs in the same request
            db.session.flush()
            
            # Mark this role group as updated
            if role_group_key and updated_role_groups is not None:
                updated_role_groups.add(role_group_key)
            
            current_app.logger.info(f"LOG {log.id}: RoleService.assign_meeting_role completed")
        
        # Always update basic fields regardless of whether owner logic was triggered or skipped
        log.Type_ID = type_id
        log.project_code = project_code

        # Update targets in OwnerMeetingRoles if provided
        # Per-owner targets take priority over shared credential
        owner_targets = item.get('owner_targets') or {}
        if (credentials or owner_targets) and owner_contacts:
            role_obj = session_type.role if session_type else None
            if role_obj and meeting_id:
                omr_records = OwnerMeetingRoles.query.filter_by(
                    meeting_id=meeting_id,
                    role_id=role_obj.id
                ).all()
                for omr in omr_records:
                    if omr.contact_id in [c.id for c in owner_contacts]:
                        # For single owner roles, ensure it matches this specific session log
                        if role_obj.has_single_owner and omr.session_log_id != log.id:
                            continue
                        
                        contact_str = str(omr.contact_id)
                        # We use owner_targets for pathway and level
                        if contact_str in owner_targets:
                            target = owner_targets[contact_str]
                            if target:
                                p_val = target.get('pathway')
                                omr.target_pathway = None if p_val == "Non Pathway" else p_val
                                if p_val == "Non Pathway" or not omr.target_pathway:
                                    omr.target_level = None
                                else:
                                    omr.target_level = target.get('level')
                        if credentials:
                            omr.credential = credentials



def _recalculate_start_times(meetings_to_update):
    for meeting in meetings_to_update:
        if not meeting or not meeting.Start_Time or not meeting.Meeting_Date:
            continue

        current_time = meeting.Start_Time
        # Fetch Is_Hidden along with Is_Section
        logs_to_update = db.session.query(SessionLog, SessionType.Is_Section, SessionType.Is_Hidden)\
            .join(SessionType, SessionLog.Type_ID == SessionType.id, isouter=True)\
            .filter(SessionLog.meeting_id == meeting.id)\
            .order_by(SessionLog.Meeting_Seq.asc()).all()

        for log, is_section, is_hidden_type in logs_to_update:
            # Calculate duration first
            duration_val = int(log.Duration_Max or 0)
            
            # Determine if session is hidden (snapshot override or type default)
            is_hidden = log.hidden if log.hidden is not None else is_hidden_type

            # If the session is a section header OR hidden OR its duration is 0,
            # set its time to None and continue (skip time accumulation).
            if is_section or is_hidden or duration_val == 0:
                log.Start_Time = None
                continue

            # The rest of the logic only runs for visible, non-section items.
            log.Start_Time = current_time
            duration_to_add = duration_val
            break_minutes = 1
            # For "Multiple shots" style (ge_mode=1), add an extra minute break after each evaluation
            EVAL_ID = SessionType.get_id_by_title('Evaluation', meeting.club_id)
            if log.Type_ID == EVAL_ID and meeting.ge_mode == 1:
                break_minutes += 1
            dt_current_time = datetime.combine(
                meeting.Meeting_Date, current_time)
            next_dt = dt_current_time + \
                timedelta(minutes=duration_to_add + break_minutes)
            current_time = next_dt.time()
def recalculate_section_ids(meeting):
    """
    Groups all sessions by sections.
    The section_id is the session id of a section.
    The section_id of a section is its own id.
    For non-section sessions, it is the ID of the section they belong to.
    """
    if not meeting:
        return
    
    if isinstance(meeting, int):
        meeting = db.session.get(Meeting, meeting)
        if not meeting:
            return

    # Fetch all session logs for the meeting ordered by Meeting_Seq ascending.
    logs = SessionLog.query.filter_by(meeting_id=meeting.id).order_by(SessionLog.Meeting_Seq.asc()).all()
    current_section_id = None
    for log in logs:
        is_section = log.session_type.Is_Section if log.session_type else False
        if is_section:
            current_section_id = log.id
            log.section_id = log.id
        else:
            log.section_id = current_section_id


def _get_processed_logs_data(meeting_id, show_media=False):
    """
    Fetches and processes session logs for a given meeting.
    Returns the list of log dictionaries ready for the frontend.
    """
    club_id = get_current_club_id()
    if meeting_id:
        query = Meeting.query.options(
            orm.joinedload(Meeting.best_table_topic_speaker),
            orm.joinedload(Meeting.best_evaluator),
            orm.joinedload(Meeting.best_speaker),
            orm.joinedload(Meeting.best_role_taker),
            orm.joinedload(Meeting.best_debater),
            orm.joinedload(Meeting.media),
            orm.joinedload(Meeting.sharing_master)
        ).filter(Meeting.id == meeting_id)
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
        if selected_meeting.best_debater_id:
            award_winners.add(('debater', selected_meeting.best_debater_id))

    # --- Fetch Raw Data ---
    raw_session_logs = _get_agenda_logs(meeting_id)
    
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

    # Cache OwnerMeetingRoles credentials and targets for functional roles
    omr_credentials = {}
    omr_targets = {}
    if meeting_id:
        omrs = OwnerMeetingRoles.query.filter_by(meeting_id=meeting_id).all()
        for omr in omrs:
            omr_credentials[(omr.role_id, omr.contact_id, omr.session_log_id)] = omr.credential
            if omr.session_log_id is not None:
                if (omr.role_id, omr.contact_id, None) not in omr_credentials:
                    omr_credentials[(omr.role_id, omr.contact_id, None)] = omr.credential
            # We want to serialize target_pathway even if it is None (representing 'Non Pathway')
            target_data = {
                'pathway': omr.target_pathway if omr.target_pathway is not None else 'Non Pathway',
                'level': omr.target_level
            }
            omr_targets[(omr.role_id, omr.contact_id, omr.session_log_id)] = target_data
            if omr.session_log_id is not None:
                if (omr.role_id, omr.contact_id, None) not in omr_targets:
                    omr_targets[(omr.role_id, omr.contact_id, None)] = target_data
    
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
        owners = log.owners # List of owners
        primary_owner = owners[0] if owners else None
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
            context_path = log.pathway
            if not context_path:
                context_path = primary_owner.Current_Path if (primary_owner and primary_owner.Current_Path) else None
            
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
        # Simplified award check
        if log.owners and session_type and session_type.role:
            role_award_category = session_type.role.award_category
            
            # Check if ANY owner is in the winners set
            # winners set has (category, id)
            if role_award_category:
                 for own in log.owners:
                     if (role_award_category, own.id) in award_winners:
                         award_type = role_award_category.replace('-', ' ').title()
                         break

        speaker_is_dtm = False
        if session_type and session_type.Title == 'Evaluation' and log.Session_Title:
            if log.Session_Title in speaker_dtm_cache and speaker_dtm_cache[log.Session_Title]:
                speaker_is_dtm = True

        role_id = session_type.role_id if (session_type and session_type.role) else None
        has_single_owner = session_type.role.has_single_owner if (session_type and session_type.role) else True
        session_log_id = log.id if has_single_owner else None

        session_owner_targets = {}
        if role_id:
            for o in owners:
                target = omr_targets.get((role_id, o.id, log.id))
                if not target:
                    target = omr_targets.get((role_id, o.id, None))
                if target:
                    session_owner_targets[str(o.id)] = target

        def get_owner_credential(o):
            if not o:
                return ''
            custom_cred = omr_credentials.get((role_id, o.id, session_log_id))
            if custom_cred:
                return custom_cred
            return derive_credentials(o)

        log_dict = {
            # SessionLog fields
            'id': log.id,
            'section_id': log.section_id,
            'Project_ID': log.Project_ID,
            'Meeting_Number': log.Meeting_Number,
            'Meeting_Seq': log.Meeting_Seq,
            'Start_Time_str': log.Start_Time.strftime('%H:%M') if log.Start_Time else '',
            'Session_Title': session_title_for_dict,
            'Type_ID': log.Type_ID,
            'Owner_ID': log.owner.id if log.owners else None,
            'owner_targets': session_owner_targets,
            'Credentials': get_owner_credential(primary_owner),
            'Duration_Min': log.Duration_Min,
            'Duration_Max': log.Duration_Max,
            'Status': log.Status,
            'project_code': log.project_code,
            # SessionType fields
            'is_section': session_type.Is_Section if session_type else False,
            'session_type_title': session_type.Title if session_type else 'Unknown Type',
            'is_hidden': log.hidden if log.hidden is not None else (session_type.Is_Hidden if session_type else False),
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
            'owner_name': " & ".join([o.Name for o in owners]) if owners else (primary_owner.Name if primary_owner else ''),
            # Detailed owner info for modals/logic (could return list)
            'owner_ids': [o.id for o in owners],
            'owners_data': [{'id': o.id, 'name': o.Name, 'dtm': o.DTM, 'club': o.get_primary_club().club_name if o.get_primary_club() else '', 'credentials': get_owner_credential(o)} for o in owners],
            
            'owner_dtm': primary_owner.DTM if primary_owner else False,
            'owner_type': primary_owner.Type if primary_owner else '',
            'owner_club': primary_owner.get_primary_club().club_name if (primary_owner and primary_owner.get_primary_club()) else '',
            'owner_completed_levels': primary_owner.Completed_Paths if primary_owner else '',
            'media_url': media.url if (show_media and media and media.url) else None,
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

        club_id = selected_meeting.club_id
        TOPICS_SPEECH_ID = SessionType.get_id_by_title('Topics Speech', club_id)
        TABLE_TOPICS_ID = SessionType.get_id_by_title('Table Topics', club_id)
        
        for i, log in enumerate(logs_data):
            if log['Type_ID'] == TOPICS_SPEECH_ID:  # Topics Speaker
                topics_speaker_sessions.append(log)
                topics_speaker_indices.append(i)
            if log['Type_ID'] == TABLE_TOPICS_ID:
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
    
    club_id = get_current_club_id()

    # --- Determine Selected Meeting ---
    is_guest = current_user.is_guest_of_club(club_id)
    
    limit_past = 8 if is_guest else None
    all_meetings, _ = get_meetings_by_status(
        limit_past=limit_past, 
        columns=[Meeting.id, Meeting.Meeting_Date, Meeting.status, Meeting.Meeting_Number],
        only_with_logs=False
    )
    meeting_ids = all_meetings
 
    selected_meeting_id_str = request.args.get('meeting_id')
    selected_meeting_num_str = request.args.get('meeting_number')
    
    selected_meeting_id = None
    if selected_meeting_id_str:
        try:
            selected_meeting_id = int(selected_meeting_id_str)
        except ValueError:
            pass
    elif selected_meeting_num_str:
        # Fallback for old links if absolutely necessary, but we should steer away
        try:
             mn = int(selected_meeting_num_str)
             club_id = get_current_club_id() # Ensure club_id is defined for the lookup
             m = Meeting.query.filter_by(Meeting_Number=mn, club_id=club_id).first()
             if m:
                 selected_meeting_id = m.id
        except ValueError:
             pass
    
    if not selected_meeting_id:
        from .utils import get_default_meeting_id
        selected_meeting_id = get_default_meeting_id()
 
        if not selected_meeting_id and meeting_ids:
            selected_meeting_id = meeting_ids[0][0]

    # --- Use Helper to Get Processed Data ---
    logs_data = []
    selected_meeting = None
    
    if selected_meeting_id:
        logs_data, selected_meeting = _get_processed_logs_data(selected_meeting_id, is_authorized(Permissions.MEDIA_MANAGE))
        
        if not selected_meeting:
             # Handle meeting not found (deleted or invalid number)
             flash(f"Meeting #{selected_meeting_id} not found or you don't have access.", "warning")
             return redirect(url_for('agenda_bp.agenda'))

        # Custom Security Check based on Status
        # 1. Unpublished: Only users with MEETING_VIEW_ALL can view full details
        if selected_meeting.status == 'unpublished':
            if not is_authorized(Permissions.MEETING_VIEW_ALL, meeting=selected_meeting):
                # Unauthorized users cannot view unpublished meetings
                # Instead of redirecting, show notice image and hide booking/voting nav
                return render_template('agenda.html',
                                       logs_data=[],
                                       meeting_ids=all_meetings,
                                       selected_meeting_id=selected_meeting_id,
                                        selected_meeting=selected_meeting,
                                       notice_image='under_planning.webp',
                                       club=db.session.get(Club, club_id),
                                       get_current_club_id=get_current_club_id,
                                       is_authorized=is_authorized,
                                       Permissions=Permissions,
                                       projects=[],
                                       pathways={},
                                       pathway_mapping={},
                                       ProjectID={},
                                       meeting_types={},
                                       next_meeting_num=0,
                                       next_meeting_date='',
                                       project_speakers=[])

        # 2. Published meetings (not started, running, finished): require MEETING_VIEW_PUBLISHED
        if selected_meeting.status in ('not started', 'running', 'finished'):
            if not is_authorized(Permissions.MEETING_VIEW_PUBLISHED, meeting=selected_meeting):
                return render_template('agenda.html',
                                       logs_data=[],
                                       meeting_ids=all_meetings,
                                       selected_meeting_id=selected_meeting_id,
                                       selected_meeting=selected_meeting,
                                       notice_image='not_started.webp',
                                       club=db.session.get(Club, club_id),
                                       get_current_club_id=get_current_club_id,
                                       is_authorized=is_authorized,
                                       Permissions=Permissions,
                                       projects=[],
                                       pathways={},
                                       pathway_mapping={},
                                       ProjectID={},
                                       meeting_types={},
                                       next_meeting_num=0,
                                       next_meeting_date='',
                                       project_speakers=[])


    # --- Other Data for Template ---
    project_speakers = _get_project_speakers(selected_meeting_id)
    
    all_pathways = Pathway.query.filter(Pathway.type != 'dummy', Pathway.status == 'active').order_by(Pathway.name).all()
    pathway_mapping = {p.name: p.abbr for p in all_pathways}
    
    pathways = {}
    for p in all_pathways:
        ptype = p.type or "Other"
        if ptype not in pathways:
            pathways[ptype] = []
        pathways[ptype].append(p.name)

    # --- Minimal Data for Initial Page Load ---
    club_id = get_current_club_id()

    # --- Template Data ---
    # We use the mapping defined in the Meeting model as the source of truth
    meeting_types = Meeting.get_type_to_template(club_id)

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
    
    # Get qualified voting candidates from voting page context
    from app.voting_routes import _get_roles_for_voting
    voting_roles = []
    if selected_meeting:
        try:
            voting_roles = _get_roles_for_voting(selected_meeting_id, selected_meeting)
        except Exception:
            pass

    voting_candidates = {
        'speaker': [],
        'evaluator': [],
        'table-topic': [],
        'role-taker': [],
        'debater': [],
        'lucky-draw-winner': [],
    }
    for r in voting_roles:
        cat = r.get('award_category')
        if cat in voting_candidates:
            oid = r.get('owner_id')
            oname = r.get('owner_name')
            if oid and oname:
                if not any(c['id'] == oid for c in voting_candidates[cat]):
                    voting_candidates[cat].append({'id': oid, 'name': oname})

    # Lucky Draw candidates: the meeting roster, deduped by contact_id,
    # excluding cancelled tickets. Mirrors the query used by the standalone
    # /lucky_draw page so both UIs offer the same pool.
    if selected_meeting:
        roster_rows = Roster.query \
            .options(db.joinedload(Roster.contact), db.joinedload(Roster.ticket)) \
            .join(Ticket, Roster.ticket_id == Ticket.id) \
            .filter(Roster.meeting_id == selected_meeting.id,
                    Ticket.name != 'Cancelled') \
            .order_by(Roster.order_number.asc()) \
            .all()
        seen_contacts = set()
        for r in roster_rows:
            if r.contact_id in seen_contacts:
                continue
            seen_contacts.add(r.contact_id)
            name = r.contact.Name if r.contact else f'Contact {r.contact_id}'
            voting_candidates['lucky-draw-winner'].append(
                {'id': r.contact_id, 'name': name})
    
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
                           meeting_ids=meeting_ids,
                           selected_meeting_id=selected_meeting_id,
                           selected_meeting=selected_meeting,  # Pass the Meeting object
                           members=members,                 # If needed elsewhere
                           projects=dropdown_data['projects'],
                           project_speakers=project_speakers,  # For JS
                           meeting_types=meeting_types,
                           default_start_time=default_start_time,
                           next_meeting_num=next_meeting_num,
                           next_meeting_date=next_meeting_date,
                           ProjectID=project_id_dict,
                           voting_candidates=voting_candidates)


# --- API Endpoints for Asynchronous Data Loading ---

@agenda_bp.route('/api/data/all')
@login_required
@authorized_club_required
def get_all_data_for_modals():
    """
A single endpoint to fetch all data needed for the agenda modals.
    This is called once by the frontend after the initial page load.
    """
    # Session Types - Filtered by club
    club_id = get_current_club_id()
    session_types = SessionType.get_all_for_club(club_id)
    session_types_data = [
        {
            "id": s.id, "Title": s.Title, "Is_Section": s.Is_Section,
            "Valid_for_Project": s.Valid_for_Project,
            "Role": s.role.name if s.role else '', "Role_Group": s.role.type if s.role else '',
            "Duration_Min": s.Duration_Min, "Duration_Max": s.Duration_Max,
            "club_id": s.club_id,
            "featured": bool(s.Featured)
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
            "Next_Project": c.Next_Project,
            "registered_paths": [p['name'] for p in c.get_member_pathways()]
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

    # Meeting Roles - Filtered by club
    roles_from_db = MeetingRole.query.filter_by(club_id=club_id).all()
    meeting_roles_data = {}
    for r in roles_from_db:
        formatted_key = r.name.upper().replace(' ', '_').replace('-', '_')
        meeting_roles_data[formatted_key] = {
            "name": r.name,
            "icon": r.icon,
            "type": r.type,
            "award": r.award_category,
            "unique": r.has_single_owner # Map database has_single_owner to legacy 'unique' property
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
        },
        'global_club_id': GLOBAL_CLUB_ID
    })




@agenda_bp.route('/agenda/export/<int:meeting_id>')
@login_required
@authorized_club_required
def export_agenda(meeting_id):
    from app.club_context import is_module_enabled
    from flask import abort
    if not is_module_enabled('Data/Slides Export'):
        abort(404)
    """
    Generates a multi-sheet XLSX export of the agenda using the ExportService.
    """
    # Find meeting to get club context
    meeting = Meeting.query.get(meeting_id)
    if not meeting:
        return "Meeting not found", 404
        
    output = MeetingExportService.generate_meeting_xlsx(meeting_id)
    if not output:
        return "Error generating XLSX", 500

    filename = f"Agenda_{meeting.Meeting_Date.strftime('%Y-%m-%d')}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@agenda_bp.route('/agenda/export_template', methods=['POST'])
@login_required
@authorized_club_required
def export_meeting_template():
    """
    Exports the current meeting structure as a CSV template file
    in the club's resource folder.
    """
    if not is_authorized(Permissions.MEETING_MANAGE):
        return jsonify(success=False, message="Permission denied"), 403

    data = request.get_json()
    meeting_id = data.get('meeting_id')
    template_name = data.get('template_name')

    if not meeting_id or not template_name:
        return jsonify(success=False, message="Meeting ID and Template Name are required"), 400

    meeting = db.session.get(Meeting, meeting_id)
    if not meeting:
        return jsonify(success=False, message="Meeting not found"), 404

    club_id = get_current_club_id()
    if meeting.club_id != club_id:
        return jsonify(success=False, message="Unauthorized"), 403

    # Fetch logs
    logs = SessionLog.query.filter_by(meeting_id=meeting_id).order_by(SessionLog.Meeting_Seq.asc()).all()

    # Sanitize filename: replace spaces with _ and add .csv
    safe_name = template_name.strip().replace(' ', '_')
    if not safe_name:
        return jsonify(success=False, message="Invalid template name"), 400
    
    filename = f"{safe_name}.csv"

    # Target folder: static/club_resources/<club_id>/templates/
    templates_dir = os.path.join(current_app.static_folder, 'club_resources', str(club_id), 'templates')
    os.makedirs(templates_dir, exist_ok=True)
    filepath = os.path.join(templates_dir, filename)

    try:
        # Write CSV content: Type,Title,Role,Owner,Duration_Min,Duration_Max,Hidden
        with open(filepath, mode='w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['Type', 'Title', 'Role', 'Owner', 'Duration_Min', 'Duration_Max', 'Hidden'])
            
            for log in logs:
                st = log.session_type
                role_name = st.role.name if st and st.role else ""
                type_title = st.Title if st else ""
                
                # Reset Title to Type title unless it's a Section or Generic type
                session_title = log.Session_Title or ""
                if type_title and type_title not in ["Section", "Generic"]:
                    session_title = type_title
                
                writer.writerow([
                    type_title,
                    session_title,
                    role_name,
                    "", # Owner column blank as requested
                    log.Duration_Min if log.Duration_Min is not None else 0,
                    log.Duration_Max if log.Duration_Max is not None else "",
                    "true" if log.hidden else ""
                ])
                
        return jsonify(success=True, message=f"Template '{filename}' exported successfully to your club resources.")
    except Exception as e:
        current_app.logger.error(f"Error exporting template: {str(e)}")
        return jsonify(success=False, message=str(e)), 500


@agenda_bp.route('/agenda/delete_template', methods=['POST'])
@login_required
@authorized_club_required
def delete_meeting_template():
    """
    Deletes a club-specific meeting template CSV file.
    """
    if not is_authorized(Permissions.MEETING_MANAGE):
        return jsonify(success=False, message="Permission denied"), 403

    data = request.get_json()
    template_name = data.get('template_name')

    if not template_name:
        return jsonify(success=False, message="Template name is required"), 400

    club_id = get_current_club_id()
    
    # Get mapping to find the filename
    type_to_template = Meeting.get_type_to_template(club_id)
    filename = type_to_template.get(template_name)
    
    if not filename:
        return jsonify(success=False, message=f"Template '{template_name}' not found"), 404
        
    template_path = Meeting.get_template_path(club_id, filename)
    
    # Security check: Ensure we are only deleting files within the club's resource folder
    club_resources_dir = os.path.abspath(os.path.join(current_app.static_folder, 'club_resources', str(club_id)))
    abs_template_path = os.path.abspath(template_path)
    
    if not abs_template_path.startswith(club_resources_dir):
        return jsonify(success=False, message="Cannot delete templates outside of club resources"), 403

    if not os.path.exists(template_path):
        return jsonify(success=False, message="Template file not found on disk"), 404

    try:
        os.remove(template_path)
        return jsonify(success=True, message=f"Template '{template_name}' deleted successfully.")
    except Exception as e:
        current_app.logger.error(f"Error deleting template: {str(e)}")
        return jsonify(success=False, message=str(e)), 500


@agenda_bp.route('/agenda/ppt/<int:meeting_id>')
@login_required
@authorized_club_required
def download_pptx_agenda(meeting_id):
    from app.club_context import is_module_enabled
    from flask import abort
    if not is_module_enabled('Data/Slides Export'):
        abort(404)
    """
    Generates a PPTX agenda for the meeting.
    """
    # Find meeting to get club context
    meeting = Meeting.query.get(meeting_id)
    if not meeting:
        return "Meeting not found", 404
        
    # v2 Integration: Pre-process agenda data to pass to the layout-based service
    logs_data, _ = _get_processed_logs_data(meeting_id)
    output = MeetingSlideService.generate_meeting_pptx(meeting_id, logs_data)
    if not output:
        return "Could not generate PPTX. Template might be missing or error occurred.", 500

    filename = f"Meeting_{meeting.Meeting_Number}_{meeting.Meeting_Date.strftime('%Y-%m-%d')}.pptx"

    return send_file(
        output,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation'
    )




class SuspiciousDateError(ValueError):
    """Exception raised when a meeting date is earlier than existing meetings."""
    pass


def _validate_meeting_form_data(form):
    """Parses and validates meeting form data."""
    meeting_id = form.get('meeting_id')
    meeting_type = form.get('meeting_type')
    club_id = get_current_club_id()
    
    # Check template validity using the model's mapping
    template_file = Meeting.get_type_to_template(club_id).get(meeting_type)
    if not template_file:
         raise ValueError(f"Invalid meeting type: {meeting_type}")
         
    template_path = Meeting.get_template_path(club_id, template_file)
    
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
        'meeting_id': meeting_id, # Keep meeting_id for upsert logic
        'meeting_number': form.get('meeting_number'), # Keep meeting_number for new meeting creation
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
    meeting = Meeting.query.get(data.get('meeting_id'))

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
        meeting.sync_excomm()
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
        meeting.sync_excomm()

    if is_new:
        # Auto-add Officers to Roster
        from .models import ContactClub
        club_id = get_current_club_id()
        if club_id:
            # Find all officers for this club
            officers = ContactClub.query.filter_by(club_id=club_id, is_officer=True).all()
            
            # Pre-fetch Officer ticket
            from .models import Ticket
            officer_ticket = Ticket.query.filter_by(name='Officer', club_id=club_id).first()
            
            for i, membership in enumerate(officers):
                roster_entry = Roster(
                    meeting_id=meeting.id,
                    contact_id=membership.contact_id,
                    order_number=None,
                    ticket=officer_ticket,
                    contact_type='Officer'
                )
                db.session.add(roster_entry)

    return meeting


def _generate_logs_from_template(meeting, template_file):
    """Reads the CSV template and generates session logs."""
    # Clear existing owners/roles first (to avoid FK constraints)
    if meeting.id:
        OwnerMeetingRoles.query.filter_by(meeting_id=meeting.id).delete(synchronize_session=False)

    # Clear existing logs
    if meeting.id:
        SessionLog.query.filter_by(meeting_id=meeting.id).delete()
    
    template_path = Meeting.get_template_path(meeting.club_id, template_file)
        
    # Get current ExComm team from database for officer auto-population
    from .models import ExComm
    club_id = get_current_club_id()
    excomm = None
    excomm_officers = {}
    
    if club_id:
        # Resolve the correct ExComm team for this meeting's date
        excomm = meeting.get_excomm()
        
        if excomm:
            # Build officer mapping from ExComm model
            excomm_officers = excomm.get_officers()  # Returns dict like {'President': Contact, 'VPE': Contact, ...}

            # Load all available session types for this club (Local + Global)
    all_session_types = SessionType.get_all_for_club(club_id)
    session_types_map = {st.Title: st for st in all_session_types}

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
            hidden_val = get_col(6)  # Optional Hidden flag
            
            # Resolve common IDs for the club
            GENERIC_ID = SessionType.get_id_by_title('Generic', club_id)
            GE_REPORT_ID = SessionType.get_id_by_title('General Evaluation Report', club_id)
            EVALUATION_ID = SessionType.get_id_by_title('Evaluation', club_id)

            # --- Resolve Session Type ---
            session_type = None
            type_id = GENERIC_ID
            if type_val:
                # Use lookup map instead of direct query to support inheritance
                session_type = session_types_map.get(type_val)
                if session_type:
                    type_id = session_type.id
            
            # --- Resolve Session Title ---
            session_title_for_log = title_val or type_val
            if not title_val and session_type:
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
            if type_id == GE_REPORT_ID:  # General Evaluation Report
                if meeting.ge_mode == 1: # Distributed
                    duration_max = 3
                else:  # 0: Traditional
                    duration_max = 5
            
            break_minutes = 1
            if type_id == EVALUATION_ID and meeting.ge_mode == 1:  # Individual Evaluation
                break_minutes += 1

            # --- Resolve Owner ---
            owner_id = None
            credentials = ''
            if owner_val:
                owner = Contact.query.join(ContactClub).filter(
                    Contact.Name == owner_val, 
                    ContactClub.club_id == club_id
                ).first()
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
            # Fetch contact to assign as owner if needed
            owner_contact = db.session.get(Contact, owner_id) if owner_id else None

            # Determine if session is hidden based on template column
            is_hidden = hidden_val and hidden_val.lower() == 'true'

            new_log = SessionLog(
                meeting_id=meeting.id,
                Meeting_Seq=seq,
                Type_ID=type_id,
                # Owner_ID and credentials removed
                Duration_Min=duration_min,
                Duration_Max=duration_max,
                Session_Title=session_title_for_log,
                Status='Booked',
                hidden=is_hidden
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
            db.session.flush()

            if owner_contact:
                # Ensure session_type is available for RoleService
                if not new_log.session_type and session_type:
                    new_log.session_type = session_type
                
                from .services.role_service import RoleService
                RoleService.assign_meeting_role(new_log, [owner_contact.id], is_admin=True)
            seq += 1

        recalculate_section_ids(meeting)


@agenda_bp.route('/agenda/create', methods=['POST'])
@login_required
@authorized_club_required
def create_from_template():
    # Check if user has permission to create agenda
    if not is_authorized(Permissions.MEETING_CREATE):
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
            'redirect_url': url_for('agenda_bp.agenda', meeting_id=meeting.id)
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating meeting: {e}")
        return jsonify({'success': False, 'message': f'Error processing template: {str(e)}'}), 500


@agenda_bp.route('/agenda/update', methods=['POST'])
@login_required
@authorized_club_required
@club_permission_required(Permissions.MEETING_MANAGE)
def update_logs():
    data = request.get_json()

    meeting_id = data.get('meeting_id')
    agenda_data = data.get('agenda_data', [])
    new_mode = int(data.get('ge_mode', 0)) if data.get('ge_mode') is not None else None
    new_meeting_title = data.get('meeting_title')
    new_meeting_type = data.get('meeting_type')
    new_subtitle = data.get('subtitle')
    new_wod = data.get('wod')
    new_media_url = data.get('media_url')
    new_meeting_number = data.get('meeting_number')

    if not meeting_id:
        return jsonify(success=False, message="Meeting ID is missing"), 400

    try:
        club_id = get_current_club_id()
        meeting = Meeting.query.get(meeting_id)
        if not meeting or (club_id and meeting.club_id != club_id):
            return jsonify(success=False, message="Meeting not found or access denied"), 404

        # Update Meeting Number — only if the field was provided and parses to
        # a positive integer. The DB-level composite unique on
        # (club_id, Meeting_Number) enforces the in-club invariant, but we
        # check explicitly so the user gets a clear error message instead of
        # a generic IntegrityError.
        if new_meeting_number is not None and new_meeting_number != '':
            try:
                n = int(new_meeting_number)
            except (ValueError, TypeError):
                return jsonify(success=False, message="Meeting Number must be a positive integer."), 400
            if n < 1:
                return jsonify(success=False, message="Meeting Number must be a positive integer."), 400
            if n != meeting.Meeting_Number:
                clash = Meeting.query.filter(
                    Meeting.club_id == meeting.club_id,
                    Meeting.Meeting_Number == n,
                    Meeting.id != meeting.id,
                ).first()
                if clash:
                    return jsonify(
                        success=False,
                        message=f"Meeting #{n} already exists in this club.",
                    ), 400
                meeting.Meeting_Number = n

        if new_meeting_title is not None:
            meeting.Meeting_Title = new_meeting_title

        if new_meeting_type is not None:
            meeting.type = new_meeting_type

        if new_subtitle is not None:
            meeting.Subtitle = new_subtitle

        if new_wod is not None:
            meeting.WOD = new_wod

        # Update Awards
        def parse_award_id(val):
            if val == "":
                return None
            elif val is not None:
                try:
                    return int(val)
                except (ValueError, TypeError):
                    pass
            return None

        if 'best_speaker_id' in data:
            meeting.best_speaker_id = parse_award_id(data.get('best_speaker_id'))
        if 'best_evaluator_id' in data:
            meeting.best_evaluator_id = parse_award_id(data.get('best_evaluator_id'))
        if 'best_table_topic_id' in data:
            meeting.best_table_topic_id = parse_award_id(data.get('best_table_topic_id'))
        if 'best_role_taker_id' in data:
            meeting.best_role_taker_id = parse_award_id(data.get('best_role_taker_id'))
        if 'best_debater_id' in data:
            # Best Debater is meaningful only on Debate-type meetings. Mirror
            # the client-side gate server-side so a stale or crafted request
            # cannot set a debater on, say, a Keynote Speech meeting.
            if meeting.type != 'Debate':
                return jsonify(
                    success=False,
                    message="Best Debater can only be set on Debate-type meetings.",
                ), 400
            meeting.best_debater_id = parse_award_id(data.get('best_debater_id'))
        if 'lucky_draw_winner_id' in data:
            meeting.lucky_draw_winner_id = parse_award_id(data.get('lucky_draw_winner_id'))

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

        # Update Meeting Date
        new_meeting_date = data.get('meeting_date')
        if new_meeting_date:
            try:
                meeting.Meeting_Date = datetime.strptime(new_meeting_date, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass

        # Commit changes to the meeting object before processing logs
        db.session.commit()

        if new_mode is not None:
            # Update the duration for the GE Report session if it exists
            club_id = get_current_club_id()
            GE_REPORT_ID = SessionType.get_id_by_title('General Evaluation Report', club_id)
            for item in agenda_data:
                # Use name comparison as fallback if ID doesn't match
                if str(item.get('type_id')) == str(GE_REPORT_ID):
                    if new_mode == 1:
                        item['duration_max'] = 3
                    else:  # 0
                        item['duration_max'] = 5
                    break

        updated_role_groups = set()
        for seq, item in enumerate(agenda_data, 1):
            _create_or_update_session(item, meeting.id, seq, updated_role_groups)

        _recalculate_start_times([meeting])
        recalculate_section_ids(meeting)

        # Recompute sharing master from the now-updated session logs and
        # owners. Same logic as the backfill CLI / migration, run on every
        # edit-mode exit so the calendar stays in sync without a manual run.
        meeting.update_sharing_master()

        db.session.commit()
        
        RoleService._clear_meeting_cache(meeting_id)

        # Return updated logs for client-side rendering
        logs_data, _ = _get_processed_logs_data(meeting_id, is_authorized(Permissions.MEDIA_MANAGE))
        project_speakers = _get_project_speakers(meeting_id)

        return jsonify(success=True, logs_data=logs_data, project_speakers=project_speakers)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500

@agenda_bp.route('/api/agenda/get_logs/<int:meeting_id>')
@login_required
@authorized_club_required
def get_logs(meeting_id):
    """
    API endpoint to fetch current logs data for a meeting.
    Used for "Fast Cancel" to revert edits without reloading the page.
    """
    try:
        # Security check: Ensure meeting belongs to current club
        club_id = get_current_club_id()
        meeting = Meeting.query.get(meeting_id)
        if not meeting or (club_id and meeting.club_id != club_id):
             return jsonify(success=False, message="Meeting not found or access denied"), 404
 
        logs_data, _ = _get_processed_logs_data(meeting_id, is_authorized(Permissions.MEDIA_MANAGE))
        project_speakers = _get_project_speakers(meeting_id)
        
        meeting_info = {
            'id': meeting.id,
            'status': meeting.status,
            'title': meeting.Meeting_Title or f"Meeting {meeting.Meeting_Number}",
            'subtitle': meeting.Subtitle or '',
            'wod': meeting.WOD or ''
        }
        
        return jsonify(success=True, logs_data=logs_data, project_speakers=project_speakers, meeting_info=meeting_info)
    except Exception as e:
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
        if log.owners:
            from .services.role_service import RoleService
            RoleService.cancel_meeting_role(log, log.owners[0].id, is_admin=True)

        # Robust Deletion: Manually clear waitlists to avoid IntegrityError if ORM cascade fails
        from .models.roster import Waitlist
        waitlist_entries = Waitlist.query.filter_by(session_log_id=log.id).all()
        for entry in waitlist_entries:
            db.session.delete(entry)
        db.session.flush()

        meeting = log.meeting
        db.session.delete(log)
        db.session.flush()
        if meeting:
            recalculate_section_ids(meeting)
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
    ).filter(Vote.meeting_id == meeting.id)\
     .group_by(Vote.award_category, Vote.contact_id)\
     .all()

    # Process votes for each category
    category_votes = {}  # {'speaker': [(contact_id, count), ...]}
    for category, contact_id, count in vote_counts:
        if not category:
            continue
        if category not in category_votes:
            category_votes[category] = []
        category_votes[category].append((contact_id, count))

    winners = {}  # {'speaker': winner_contact_id}
    for category, candidate_votes in category_votes.items():
        if not candidate_votes:
            continue
        # Find maximum vote count for this category
        max_votes = max(count for _, count in candidate_votes)
        # Find all candidates with the maximum vote count
        candidates = [contact_id for contact_id, count in candidate_votes if count == max_votes and contact_id is not None]
        if not candidates:
            continue

        if len(candidates) == 1:
            winners[category] = candidates[0]
        else:
            # Tie-breaker: choose the one who wins that award less historically in this club
            award_attr = f"best_{category.replace('-', '_')}_id"
            if hasattr(Meeting, award_attr):
                win_counts = {}
                for cid in candidates:
                    win_count = db.session.query(func.count(Meeting.id)).filter(
                        Meeting.club_id == meeting.club_id,
                        getattr(Meeting, award_attr) == cid,
                        Meeting.id != meeting.id
                    ).scalar() or 0
                    win_counts[cid] = win_count
                
                # Choose the candidate with the minimum win count (stable fallback if there's a tie in win count)
                winners[category] = min(candidates, key=lambda cid: win_counts[cid])
            else:
                winners[category] = candidates[0]

    # Update meeting object with winners
    for category, winner_id in winners.items():
        award_attr = f"best_{category.replace('-', '_')}_id"
        if hasattr(meeting, award_attr):
            setattr(meeting, award_attr, winner_id)

    # Calculate Standard NPS: (Promoters - Detractors) / Total * 100
    # Promoters: 9-10, Detractors: 1-6, Passives: 7-8 (0s are excluded)
    scores = db.session.query(Vote.score).filter(
        Vote.meeting_id == meeting.id,
        Vote.question == "How likely are you to recommend this meeting to a friend or colleague?",
        Vote.score.isnot(None),
        Vote.score > 0
    ).all()


    
    if scores:
        scores_list = [s[0] for s in scores]
        total = len(scores_list)
        promoters = sum(1 for s in scores_list if s >= 9)
        detractors = sum(1 for s in scores_list if s <= 6)
        nps = (promoters - detractors) / total * 100
        meeting.nps = float(nps)
    else:
        meeting.nps = 0.0


@agenda_bp.route('/agenda/status/<int:meeting_id>', methods=['POST'])
@login_required
@authorized_club_required
def update_meeting_status(meeting_id):
    """Toggles the status of a meeting."""
    club_id = get_current_club_id()
    meeting = db.session.get(Meeting, meeting_id)
 
    if not meeting or (club_id and meeting.club_id != club_id):
        return jsonify(success=False, message="Meeting not found"), 404

    current_status = meeting.status
    if current_status != 'finished':
        if not is_authorized(Permissions.MEETING_MANAGE, meeting=meeting):
            return jsonify(success=False, message="Permission denied"), 403
    
    new_status = current_status

    if current_status == 'unpublished':
        new_status = 'not started'
    elif current_status == 'not started':
        new_status = 'running'
    elif current_status == 'running':
        new_status = 'finished'
        meeting.status = new_status
        # Tally votes when meeting finishes
        _tally_votes_and_set_winners(meeting)

        # Clean up waitlist entries for this meeting
        Waitlist.delete_for_meeting(meeting.id)
 
        # Sync Planner Statuses: Transition to terminal states
        plans = Planner.query.filter_by(meeting_id=meeting.id).all()
        for plan in plans:
            if plan.status == 'booked':
                plan.status = 'completed'
            elif plan.status == 'waitlist':
                plan.status = 'obsolete'
            # 'draft' stays 'draft' - user can move it to another meeting later

        # Auto-complete all projects of this meeting
        for log in meeting.session_logs:
            is_prepared_speech = log.project and log.project.is_prepared_speech
            is_project = (log.session_type and log.session_type.Valid_for_Project and log.Project_ID and log.Project_ID != ProjectID.GENERIC) or is_prepared_speech
            if is_project:
                log.Status = 'Completed'
                # Sync metadata for owners
                for owner in log.owners:
                    from .utils import sync_contact_metadata
                    sync_contact_metadata(owner.id, commit=False)

    elif current_status == 'finished':
        # Full deletion flow as requested
        # Check if user has permission to delete meetings
        if not is_authorized(Permissions.MEETING_CREATE):
            return jsonify(success=False, message="You do not have permission to delete meetings."), 403
            
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
        
        # Invalidate Cache
        RoleService._clear_meeting_cache(meeting.id)
        
        return jsonify(success=True, new_status=new_status)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@agenda_bp.route('/agenda/sync_tally/<int:meeting_id>', methods=['POST'])
@login_required
@authorized_club_required
def sync_tally(meeting_id):
    try:
        # Security check: Ensure meeting belongs to current club
        club_id = get_current_club_id()
        meeting = Meeting.query.get(meeting_id)
        if not meeting or (club_id and meeting.club_id != club_id):
             return jsonify(success=False, message="Meeting not found"), 404

        context = MeetingExportContext(meeting_id)
        sync_participants_to_tally(context.participants_dict)
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e)), 500
