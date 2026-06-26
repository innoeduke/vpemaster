# vpemaster/voting_routes.py

from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
from flask import Blueprint, render_template, request, session, jsonify, current_app, redirect, url_for
from .models import SessionLog, SessionType, Contact, Meeting, User, MeetingRole, Vote, AuthRole, Roster, Ticket
from . import db
from datetime import datetime
import secrets
from sqlalchemy import func, distinct
from sqlalchemy.orm import joinedload, selectinload
from flask_login import current_user
from .club_context import get_current_club_id, authorized_club_required

from .services.role_service import RoleService
from .utils import (
    get_session_voter_identifier,
    get_current_user_info,
    get_meetings_by_status,
    consolidate_session_logs,
    group_roles_by_category
)

voting_bp = Blueprint('voting_bp', __name__)


@voting_bp.before_request
def check_voting_enabled():
    from app.club_context import is_module_enabled
    from flask import abort
    if not is_module_enabled('Voting'):
        abort(404)


def get_meeting_omr_records(meeting_id):
    """Fetch all OwnerMeetingRoles for a meeting with Contact and MeetingRole, cached per-request."""
    from flask import request, has_request_context
    if has_request_context():
        cache = getattr(request, '_meeting_omr_records_cache', None)
        if cache is None:
            cache = request._meeting_omr_records_cache = {}
        if meeting_id in cache:
            return cache[meeting_id]

    from app.models import OwnerMeetingRoles, Contact, MeetingRole
    omr_records = db.session.query(OwnerMeetingRoles, Contact, MeetingRole)\
        .join(Contact, OwnerMeetingRoles.contact_id == Contact.id)\
        .outerjoin(MeetingRole, OwnerMeetingRoles.role_id == MeetingRole.id)\
        .filter(OwnerMeetingRoles.meeting_id == meeting_id)\
        .all()

    if has_request_context():
        request._meeting_omr_records_cache[meeting_id] = omr_records

    return omr_records


def populate_session_log_owners(session_logs, meeting_id):
    """Batch populates the cached owners relationship on session logs to avoid N+1 queries."""
    if not session_logs:
        return
        
    omr_records = get_meeting_omr_records(meeting_id)
        
    # Group contacts by their role_id and session_log_id
    single_owner_map = {} # (role_id, session_log_id) -> list of Contacts
    shared_owner_map = {} # role_id -> list of Contacts
    
    for omr, contact, role in omr_records:
        if not role:
            continue
        role_id = role.id
        has_single_owner = role.has_single_owner
        
        if has_single_owner:
            key = (role_id, omr.session_log_id)
            single_owner_map.setdefault(key, []).append(contact)
        else:
            shared_owner_map.setdefault(role_id, []).append(contact)
            
    # Assign cached owners to each session log
    for log in session_logs:
        if not log.session_type or not log.session_type.role:
            log._cached_owners = []
            continue
            
        role = log.session_type.role
        role_id = role.id
        has_single_owner = role.has_single_owner
        
        if has_single_owner:
            log._cached_owners = single_owner_map.get((role_id, log.id), [])
        else:
            log._cached_owners = shared_owner_map.get(role_id, [])


def _enrich_role_data_for_voting(roles_dict, selected_meeting, vote_counts=None, logs_by_id=None, user_votes=None, winners_list=None):
    """
    Enriches role data with voting-specific information (awards, vote counts).

    Args:
        roles_dict: Dictionary of consolidated roles
        selected_meeting: Meeting object
        vote_counts: Optional pre-computed {(contact_id, award_category): count}
            dict. If None, falls back to an empty dict (vote counts are
            admin-only anyway; the caller decides whether to populate this).
        logs_by_id: Optional dict {session_log_id: SessionLog} pre-loaded with
            joinedload(session_type.role). Used to resolve the first log of
            Keynote Speaker roles without a fresh db.session.get.
        user_votes: Optional list of Vote objects for the current voter.
        winners_list: Optional list of MeetingAwardWinner objects.

    Returns:
        list: Enriched roles list
    """
    if not selected_meeting:
        return []

    winner_set = set()
    if selected_meeting.status == 'running':
        # For a running meeting, the "winner" is who the current user voted for
        voter_identifier = get_session_voter_identifier()

        if voter_identifier:
            if user_votes is None:
                user_votes = Vote.query.filter_by(
                    meeting_id=selected_meeting.id,
                    voter_identifier=voter_identifier
                ).all()
            for vote in user_votes:
                if vote.award_category:
                    winner_set.add((vote.award_category, vote.contact_id))

    elif selected_meeting.status == 'finished':
        if winners_list is None:
            from .models.voting import MeetingAwardWinner
            winners = MeetingAwardWinner.query.filter_by(meeting_id=selected_meeting.id).all()
        else:
            winners = winners_list
        if winners:
            for w in winners:
                winner_set.add((w.award_category, w.contact_id))
        else:
            if selected_meeting.best_speaker_id: winner_set.add(('speaker', selected_meeting.best_speaker_id))
            if selected_meeting.best_evaluator_id: winner_set.add(('evaluator', selected_meeting.best_evaluator_id))
            if selected_meeting.best_table_topic_id: winner_set.add(('table-topic', selected_meeting.best_table_topic_id))
            if selected_meeting.best_role_taker_id: winner_set.add(('role-taker', selected_meeting.best_role_taker_id))
            if selected_meeting.best_debater_id: winner_set.add(('debater', selected_meeting.best_debater_id))

    if vote_counts is None:
        vote_counts = {}

    # role_obj is preloaded by the joinedload in _get_roles_for_voting
    # (SessionLog.session_type.role), and consolidate_session_logs skips logs
    # without a role. A missing role_obj here would indicate a data integrity
    # issue; fall through with None rather than re-querying.
    enriched_roles = []
    for _, role_data in roles_dict.items():
        role_obj = role_data.get('role_obj')

        role_data['icon'] = role_obj.icon if role_obj and role_obj.icon else "fa-question-circle"
        role_data['session_id'] = role_data['session_ids'][0]

        owner_id = role_data['owner_id']
        award_category = role_obj.award_category if role_obj else None

        if role_obj and role_obj.name == 'Keynote Speaker':
            from .constants import ProjectID
            session_ids = role_data.get('session_ids')
            first_log = None
            if session_ids and logs_by_id is not None:
                first_log = logs_by_id.get(session_ids[0])
            elif session_ids:
                # Fallback only when caller didn't supply a pre-loaded map.
                first_log = db.session.get(SessionLog, session_ids[0])

            if first_log:
                # If no project or generic project, disqualify from voting
                if not first_log.Project_ID or first_log.Project_ID == ProjectID.GENERIC:
                    award_category = None

        role_data['award_category'] = award_category
        category_has_winner = any(cat == award_category for cat, _ in winner_set)
        role_data['award_type'] = award_category if owner_id and award_category and (award_category, owner_id) in winner_set else None
        role_data['award_category_open'] = bool(award_category and not category_has_winner)
        
        # Attach vote count if available
        if vote_counts and award_category:
            role_data['vote_count'] = vote_counts.get((owner_id, award_category), 0)

        enriched_roles.append(role_data)
    
    return enriched_roles


def _sort_roles_for_voting(roles):
    """
    Sorts roles for voting view by award category priority.
    
    Args:
        roles: List of role dictionaries
    
    Returns:
        list: Sorted roles
    """
    CATEGORY_ORDER = {
        'speaker': 1,
        'evaluator': 2,
        'role-taker': 3,
        'table-topic': 4,
        'debater': 5
    }
    
    def get_category_priority(role):
        cat = role.get('award_category', '') or ''
        if cat in CATEGORY_ORDER:
            return CATEGORY_ORDER[cat]
        if cat in ('none', ''):
            return 99
        return 6

    roles.sort(key=lambda x: (
        get_category_priority(x),
        x.get('award_category', '') or '', 
        x['role']
    ))
    
    return roles


def _get_roles_for_voting(meeting_id, meeting, award_configs_list=None, user_votes=None, winners_list=None):
    """
    Helper function to get and process roles for the voting page.

    Args:
        meeting_id: Meeting ID
        meeting: Meeting object
        award_configs_list: Pre-fetched list of MeetingAwardConfig for this
            meeting. Fetched by the caller to avoid a duplicate query inside
            this function. If None, the function falls back to fetching it.
        user_votes: Optional pre-fetched list of Vote objects.
        winners_list: Optional pre-fetched list of MeetingAwardWinner objects.

    Returns:
        list: Processed roles for voting
    """
    if not meeting:
        return []
        
    # Fetch roles and enrich them
    club_id = meeting.club_id
    # Re-fetch logs with eager-loaded relationships to avoid N+1 queries during consolidation
    from sqlalchemy.orm import subqueryload
    from app.models import SessionType, Waitlist
    all_logs = SessionLog.query.filter_by(meeting_id=meeting_id)\
        .options(
            joinedload(SessionLog.session_type).joinedload(SessionType.role)
        ).all()

    populate_session_log_owners(all_logs, meeting_id)
    consolidated = consolidate_session_logs(all_logs, include_waitlist=False)
    logs_by_id = {log.id: log for log in all_logs}

    # Single aggregated vote-count query, gated by admin/track-progress perms.
    # This replaces three separate GROUP BYs that used to live in the
    # officer / role-taker / custom-config blocks below.
    can_see_vote_counts = (
        meeting.status in ('running', 'finished')
        and (
            is_authorized(Permissions.MEETING_MANAGE, meeting=meeting)
            or is_authorized(Permissions.VOTING_TRACK_PROGRESS, meeting=meeting)
        )
    )
    from .services.voting_aggregation import aggregate_votes_for_meeting
    vote_counts = (
        aggregate_votes_for_meeting(meeting_id) if can_see_vote_counts else {}
    )

    enriched_roles = _enrich_role_data_for_voting(consolidated, meeting, vote_counts, logs_by_id, user_votes, winners_list)
    
    # 4. Handle custom awards configurations & disabled awards
    from .models.voting import MeetingAwardConfig, MeetingAwardWinner
    from .agenda_routes import get_meeting_awards
    if award_configs_list is None:
        configs = MeetingAwardConfig.query.filter_by(meeting_id=meeting.id).all()
    else:
        configs = award_configs_list
    disabled_cats = {c.award_category for c in configs if c.max_votes_per_user == 0 or c.max_winners == 0}

    # The set of award categories that are actually enabled for this meeting.
    # get_meeting_awards() encapsulates the precedence:
    #   club.default_awards  ->  fallback DEFAULT_AWARD_CATEGORIES
    #     overlaid with per-meeting MeetingAwardConfig (including custom awards).
    # We then drop anything explicitly disabled (max_votes=0 or max_winners=0).
    # Standard categories (e.g. 'role-taker') that the club has NOT chosen as a
    # default award will not appear in this set, so we will not render an
    # accordion for them on the voting page.
    enabled_cats = {
        a['category'] for a in get_meeting_awards(meeting, configs_list=configs, winners_list=winners_list)
        if a['category'] not in disabled_cats
    }

    # Consolidate 'role-taker' category to one row per person
    # 1. Separate role-takers from others, dropping categories that aren't
    #    enabled for this meeting (either disabled, or never chosen as a
    #    default award for this club).
    other_roles = [
        r for r in enriched_roles
        if r.get('award_category') != 'role-taker'
        and r.get('award_category') in enabled_cats
    ]

    consolidated_role_takers = []
    if 'role-taker' in enabled_cats:
        # 2. Get all role takers for the meeting using RoleService
        role_takers_map = RoleService.get_role_takers(meeting_id, meeting.club_id)
        
        # 3. Create consolidated rows for each person who took a 'role-taker' role
        # Determine winner info for role-taker award
        voter_identifier = get_session_voter_identifier()
        user_vote_ids = set()
        if meeting.status == 'running' and voter_identifier:
            if user_votes is None:
                votes = Vote.query.filter_by(
                    meeting_id=meeting_id,
                    voter_identifier=voter_identifier,
                    award_category='role-taker'
                ).all()
            else:
                votes = [v for v in user_votes if v.award_category == 'role-taker']
            for vote in votes:
                if vote.contact_id:
                    user_vote_ids.add(vote.contact_id)
                
        role_taker_winner_ids = set()
        if meeting.status == 'finished':
            if winners_list is None:
                winners = MeetingAwardWinner.query.filter_by(meeting_id=meeting.id, award_category='role-taker').all()
            else:
                winners = [w for w in winners_list if w.award_category == 'role-taker']
            if winners:
                role_taker_winner_ids = {w.contact_id for w in winners}
            elif meeting.best_role_taker_id:
                role_taker_winner_ids.add(meeting.best_role_taker_id)

        # Vote counts for role-takers (admins only) — slice the precomputed
        # aggregate to avoid a third GROUP BY on the votes table.
        role_taker_vote_counts = {
            cid: n for (cid, cat), n in vote_counts.items()
            if cat == 'role-taker'
        }

        for contact_id_str, roles in role_takers_map.items():
            # Filter roles for this person that belong to the 'role-taker' award category
            person_role_taker_roles = [r for r in roles if r.get('award_category') == 'role-taker']
            
            if not person_role_taker_roles:
                continue
                
            contact_id = int(contact_id_str)
            first_role = person_role_taker_roles[0]
            
            # Combine and deduplicate role names: "Timer, Ah-Counter"
            role_names = []
            for r in person_role_taker_roles:
                if r['name'] not in role_names:
                    role_names.append(r['name'])
            combined_role_names = ", ".join(role_names)
            
            # Build consolidated role-taker entry
            is_winner = (contact_id in user_vote_ids) if meeting.status == 'running' else (contact_id in role_taker_winner_ids)
            category_has_winner = (len(user_vote_ids) > 0) if meeting.status == 'running' else bool(role_taker_winner_ids)

            role_entry = {
                'role': combined_role_names,
                'icon': 'fa-users', # Generic icon for consolidated roles
                'session_id': first_role.get('session_log_id'), # Might be None
                'owner_id': contact_id,
                'owner_name': first_role.get('owner_name'),
                'owner_avatar_url': first_role.get('owner_avatar_url'),
                'award_category': 'role-taker',
                'award_category_open': not category_has_winner,
                'award_type': 'role-taker' if is_winner else None,
                'vote_count': role_taker_vote_counts.get(contact_id, 0)
            }
            consolidated_role_takers.append(role_entry)

    # A custom MeetingAwardConfig should only be surfaced through the custom
    # path when the standard session-driven path has nothing for that category.
    # A hardcoded standard_cats set would wrongly drop a user-added custom
    # "Debater" award (its category collides with the built-in 'debater').
    enriched_cats = {r.get('award_category') for r in enriched_roles if r.get('award_category')}
    custom_configs = [
        c for c in configs
        if c.award_category not in enriched_cats
        and c.award_category not in disabled_cats
    ]
    
    custom_roles = []
    if custom_configs:
        # Fetch roster contacts
        roster_rows = Roster.query \
            .options(db.joinedload(Roster.contact), db.joinedload(Roster.ticket)) \
            .join(Ticket, Roster.ticket_id == Ticket.id) \
            .filter(Roster.meeting_id == meeting.id,
                    Ticket.name != 'Cancelled') \
            .order_by(Roster.order_number.asc()) \
            .all()
        seen_contacts = set()
        roster_contacts = []
        for r in roster_rows:
            if r.contact_id and r.contact_id not in seen_contacts:
                seen_contacts.add(r.contact_id)
                roster_contacts.append(r.contact)
                
        # Build winner set and vote counts for custom categories
        winner_set = set()
        voter_identifier = get_session_voter_identifier()
        if meeting.status == 'running':
            if voter_identifier:
                if user_votes is None:
                    user_votes = Vote.query.filter_by(
                        meeting_id=meeting.id,
                        voter_identifier=voter_identifier
                    ).all()
                for vote in user_votes:
                    if vote.award_category:
                        winner_set.add((vote.award_category, vote.contact_id))
        elif meeting.status == 'finished':
            if winners_list is None:
                winners = MeetingAwardWinner.query.filter_by(meeting_id=meeting.id).all()
            else:
                winners = winners_list
            for w in winners:
                winner_set.add((w.award_category, w.contact_id))
                
        # Construct meeting_role_takers in memory from cached OMR records (saves a query!)
        omr_records = get_meeting_omr_records(meeting.id)
        meeting_role_takers = []
        for omr, contact, role in omr_records:
            if role and role.type != 'officer':
                meeting_role_takers.append((contact, role.id, role.name))

        # Parse meeting_role_takers in memory to build index mappings
        # contact_role_names: contact_id -> ordered list of role names
        # contact_role_ids:   contact_id -> set of role ids
        # role_id_to_contacts: role_id -> list of Contact objects
        # role_name_to_contacts: role_name -> list of Contact objects
        contact_role_names = {}
        contact_role_ids = {}
        role_id_to_contacts = {}
        role_name_to_contacts = {}

        for contact, r_id, r_name in meeting_role_takers:
            c_id = contact.id
            contact_role_names.setdefault(c_id, [])
            contact_role_ids.setdefault(c_id, set())
            if r_name not in contact_role_names[c_id]:
                contact_role_names[c_id].append(r_name)
            contact_role_ids[c_id].add(r_id)

            # Build list of Contacts per role_id and role_name
            role_id_to_contacts.setdefault(r_id, []).append(contact)
            role_name_to_contacts.setdefault(r_name, []).append(contact)

        for config in custom_configs:
            cat = config.award_category
            category_has_winner = any(w_cat == cat for w_cat, _ in winner_set)

            # Determine candidate list
            candidates_to_use = []
            config_role_ids = None  # None = no filter (legacy / roster fallback)
            if config.role_associations:
                # New path: use the associative table
                config_role_ids = {a.meeting_role_id for a in config.role_associations}
                seen_candidates = set()
                role_takers = []
                for r_id in config_role_ids:
                    for contact in role_id_to_contacts.get(r_id, []):
                        if contact.id not in seen_candidates:
                            seen_candidates.add(contact.id)
                            role_takers.append(contact)
                candidates_to_use = role_takers
            elif config.associated_role:
                # Legacy fallback: pre-migration data, or awards never re-saved through the picker
                role_takers = role_name_to_contacts.get(config.associated_role, [])
                candidates_to_use = role_takers
            else:
                candidates_to_use = roster_contacts

            for contact in candidates_to_use:
                if not contact:
                    continue
                owner_id = contact.id
                is_winner = (cat, owner_id) in winner_set

                # Show only the role names that are actually associated with this
                # award — not every role the contact took in the meeting.
                if config_role_ids is not None:
                    assigned_roles = [
                        r_name for c, r_id, r_name in meeting_role_takers
                        if c.id == owner_id and r_id in config_role_ids
                    ]
                else:
                    assigned_roles = contact_role_names.get(owner_id, [])
                role_display_name = ", ".join(assigned_roles) if assigned_roles else 'Candidate'

                custom_role_entry = {
                    'role': role_display_name,
                    'icon': 'fa-award',
                    'session_id': None,
                    'owner_id': owner_id,
                    'owner_name': contact.Name,
                    'owner_avatar_url': contact.Avatar_URL,
                    'award_category': cat,
                    'award_category_open': not category_has_winner,
                    'award_type': cat if is_winner else None,
                    'vote_count': vote_counts.get((owner_id, cat), 0)
                }
                custom_roles.append(custom_role_entry)

    # Combine back
    final_roles = other_roles + consolidated_role_takers + custom_roles
    
    sorted_roles = _sort_roles_for_voting(final_roles)

    # Filter to only show roles with award categories
    if meeting.status in ['running', 'finished']:
        sorted_roles = [
            role for role in sorted_roles 
            if role.get('award_category') and role.get('award_category') not in ['none', '', 'None']
        ]

    return sorted_roles


def _get_voting_page_context(meeting_id):
    """Gathers context for the voting page."""
    # Logic similar to booking page but for voting
    from app.club_context import get_current_club_id
    from app.models.voting import MeetingAwardConfig
    club_id = get_current_club_id()
    
    # Show active meetings in dropdown. Skip the default-meeting lookup when
    # the caller already supplied a meeting_id — it adds 3 redundant queries.
    limit_past = None if is_authorized(Permissions.MEDIA_MANAGE) else 8
    upcoming_meetings, default_meeting_id = get_meetings_by_status(
        limit_past=limit_past,
        columns=[Meeting.id, Meeting.Meeting_Date, Meeting.status, Meeting.Meeting_Number],
        include_default=(meeting_id is None),
        only_with_logs=False,
    )
 
    if not meeting_id:
        # Stay on the meeting of today's date if the user has VOTING_VIEW_RESULTS permission
        today_date = datetime.today().date()
        today_meeting = None
        if is_authorized(Permissions.VOTING_VIEW_RESULTS):
            today_meeting_query = Meeting.query.filter(Meeting.Meeting_Date == today_date)
            if club_id:
                today_meeting_query = today_meeting_query.filter(Meeting.club_id == club_id)
            today_meeting = today_meeting_query.first()

        if today_meeting:
            meeting_id = today_meeting.id
        else:
            # Prefer the default meeting IF it is in our filtered list (running/finished)
            valid_ids = [m[0] for m in upcoming_meetings]
            if default_meeting_id and default_meeting_id in valid_ids:
                meeting_id = default_meeting_id
            else:
                # Otherwise take the most recent meeting from the list
                meeting_id = upcoming_meetings[0][0] if upcoming_meetings else None
 
    context = {
        'upcoming_meetings': upcoming_meetings,
        'selected_meeting_id': meeting_id,
        'selected_meeting': None,
        'db_status': None,
        'can_edit_meeting_status': False,
        'enriched_role_groups': [],
        'guest_info': None,
        'roles': [],
        'is_admin_view': False,
        'current_user_contact_id': None,
        'user_role': current_user.primary_role_name if current_user.is_authenticated else 'Guest',
        'best_award_ids': set(),
        'has_voted': False,
        'sorted_role_groups': [],
        'can_track_progress': False,
        'meeting_rating_score': None,
        'meeting_feedback_comment': ""
    }
 
    if not meeting_id:
        context['notice_image'] = 'not_started.webp'
        return context
 
    selected_meeting = Meeting.query.options(
        joinedload(Meeting.club),
        selectinload(Meeting.award_configs).joinedload(MeetingAwardConfig.role_associations),
    ).populate_existing().get(meeting_id)
    if not selected_meeting or (club_id and selected_meeting.club_id != club_id):
        return context

    context['db_status'] = selected_meeting.status
    context['can_edit_meeting_status'] = is_authorized(Permissions.MEETING_MANAGE, meeting=selected_meeting)

    # Check if we should override status for display and bypass notices
    is_meeting_date = selected_meeting.Meeting_Date == datetime.today().date()
    has_voting_view_results = is_authorized(Permissions.VOTING_VIEW_RESULTS, meeting=selected_meeting)

    if is_meeting_date and has_voting_view_results:
        # Eager load relations we will read after the expunge to avoid
        # DetachedInstanceError: award_winners (used below) and club (used
        # by get_meeting_awards inside _get_roles_for_voting).
        _ = selected_meeting.award_winners
        _ = selected_meeting.club
        # Expunge from session so in-memory changes are never committed
        db.session.expunge(selected_meeting)
        # Override status to 'running' if it's not already 'running' or 'finished'
        # so that it displays the voting form correctly and allows submissions.
        if selected_meeting.status not in ('running', 'finished'):
            selected_meeting.status = 'running'

    user, current_user_contact_id = get_current_user_info()
    context['current_user_contact_id'] = current_user_contact_id

    # Check if user has voted for this meeting
    voter_identifier = get_session_voter_identifier()
    user_votes = []
    if voter_identifier:
        user_votes = Vote.query.filter_by(
            meeting_id=meeting_id,
            voter_identifier=voter_identifier
        ).all()
        if user_votes:
            context['has_voted'] = True

    context['selected_meeting'] = selected_meeting

    # Reuses the eager-loaded award_configs (saves a duplicate query).
    award_configs_list = selected_meeting.award_configs if selected_meeting else []
    context['award_configs_list'] = award_configs_list

    # Calculate total received votes (unique voters)
    total_voters = db.session.query(func.count(distinct(Vote.voter_identifier)))\
        .filter(Vote.meeting_id == meeting_id)\
        .scalar() or 0
    context['total_voters'] = total_voters

    # --- Access Control Logic ---
    status = selected_meeting.status
    
    if status == 'unpublished':
        context['notice_image'] = 'under_planning.webp'
    elif status == 'cancelled':
        context['notice_image'] = 'booking_closed.webp'

    elif status in ('not started', 'running', 'finished'):
        if status == 'not started':
            context['notice_image'] = 'not_started.webp'
        elif not is_authorized(Permissions.MEETING_VIEW_PUBLISHED, meeting=selected_meeting):
            context['notice_image'] = 'not_started.webp'
        elif status == 'finished':
            # Finished: only those with VOTING_VIEW_RESULTS can see results
            if not is_authorized(Permissions.VOTING_VIEW_RESULTS, meeting=selected_meeting):
                context['notice_image'] = 'not_started.webp'
    
    # Status 'running' is open to everyone for voting

    # is_admin_view controls seeing results/accordion (Admin, Officer, VPE, Manager)
    context['is_admin_view'] = is_authorized(Permissions.VOTING_VIEW_RESULTS, meeting=selected_meeting)
    
    # can_track_progress controls seeing results WHILE running (Admin only)
    context['can_track_progress'] = is_authorized(Permissions.VOTING_TRACK_PROGRESS, meeting=selected_meeting)

    # Use selected_meeting.award_winners (lazy loaded on finished meetings)
    winners_list = selected_meeting.award_winners if (selected_meeting and selected_meeting.status == 'finished') else []
    roles = _get_roles_for_voting(
        meeting_id,
        selected_meeting,
        award_configs_list=award_configs_list,
        user_votes=user_votes,
        winners_list=winners_list
    )
    context['roles'] = roles
    context['sorted_role_groups'] = group_roles_by_category(roles)
    context['best_award_ids'] = selected_meeting.get_best_award_ids() if (selected_meeting and selected_meeting.status == 'finished') else set()

    # Build award_configs lookup from the same list fetched above
    context['award_configs'] = {}
    for config in award_configs_list:
        context['award_configs'][config.award_category] = {
            'max_votes': config.max_votes_per_user,
            'max_winners': config.max_winners
        }

    # Extract existing meeting rating and feedback from the pre-fetched user_votes in memory
    context['meeting_rating_score'] = None
    context['meeting_feedback_comment'] = ""
    for vote in user_votes:
        if vote.question == "How likely are you to recommend this meeting to a friend or colleague?":
            context['meeting_rating_score'] = vote.score
        elif vote.question == "More feedback/comments":
            context['meeting_feedback_comment'] = vote.comments

    return context


@voting_bp.route('/voting', defaults={'meeting_id': None}, methods=['GET'])
@voting_bp.route('/voting/<int:meeting_id>', methods=['GET'])
@authorized_club_required
def voting(meeting_id):
    """Main voting page route."""
    from flask import make_response
    from flask_login import current_user
    from app.club_context import get_current_club_id
    from app import cache

    # Anonymous (guest) views share an identical render — same meeting, no
    # per-session voter_token embedded in HTML. Cache the rendered response
    # keyed only on (club_id, meeting_id) so the cache lookup happens BEFORE
    # any DB queries. The 30s TTL bounds staleness on `total_voters` and
    # other vote-driven fields; batch_vote / vote_for_award bust this key.
    # Authenticated users get a per-session render and skip the cache.
    is_cacheable = not current_user.is_authenticated
    cache_key = None
    if is_cacheable:
        club_id = get_current_club_id()
        cache_key = f"voting_html_guest_{club_id}_{meeting_id or 'default'}"
        cached_html = cache.get(cache_key)
        if cached_html is not None:
            resp = make_response(cached_html)
            resp.headers['Cache-Control'] = 'private, max-age=10'
            return resp

    context = _get_voting_page_context(meeting_id)
    rendered = render_template('voting.html', **context)

    if is_cacheable:
        cache.set(cache_key, rendered, timeout=30)

    resp = make_response(rendered)
    resp.headers['Cache-Control'] = 'private, max-age=10'
    return resp


@voting_bp.route('/voting/batch_vote', methods=['POST'])
def batch_vote():
    """Batch vote submission endpoint."""
    data = request.get_json()
    meeting_id = data.get('meeting_id')
    votes = data.get('votes', [])

    if not meeting_id:
        return jsonify(success=False, message="Missing meeting ID."), 400

    club_id = get_current_club_id()
    meeting_query = Meeting.query.filter_by(id=meeting_id)
    if club_id:
        meeting_query = meeting_query.filter(Meeting.club_id == club_id)
    meeting = meeting_query.first()
    if not meeting:
        return jsonify(success=False, message="Meeting not found."), 404

    is_meeting_date = meeting.Meeting_Date == datetime.today().date()
    has_voting_view_results = is_authorized(Permissions.VOTING_VIEW_RESULTS, meeting=meeting)

    if meeting.status != 'running' and not (meeting.status != 'finished' and is_meeting_date and has_voting_view_results):
        return jsonify(success=False, message="Voting is not active for this meeting."), 403

    # Determine voter identity
    voter_identifier = get_session_voter_identifier()
    if not voter_identifier:
        if 'voter_token' not in session:
            session['voter_token'] = secrets.token_hex(16)
        voter_identifier = session['voter_token']

    try:
        # Clear previous votes for this voter in this meeting
        Vote.query.filter_by(
            meeting_id=meeting_id,
            voter_identifier=voter_identifier
        ).delete()
        
        # Load configs to get disabled categories and max votes
        from .models.voting import MeetingAwardConfig
        configs = MeetingAwardConfig.query.filter_by(meeting_id=meeting_id).all()
        disabled_cats = {c.award_category for c in configs if c.max_votes_per_user == 0 or c.max_winners == 0}
        
        category_votes_count = {}
        
        # Add new votes
        for v in votes:
            contact_id = v.get('contact_id')
            award_category = v.get('award_category')
            if contact_id and award_category:
                if award_category in disabled_cats:
                    continue
                
                # Enforce max votes per user limit (capping at max_votes or max_winners)
                config_item = next((c for c in configs if c.award_category == award_category), None)
                max_votes_allowed = 1
                if config_item:
                    max_votes_allowed = min(config_item.max_votes_per_user, config_item.max_winners)
                
                category_votes_count[award_category] = category_votes_count.get(award_category, 0) + 1
                if category_votes_count[award_category] > max_votes_allowed:
                    continue

                new_vote = Vote(
                    meeting_id=meeting_id,
                    voter_identifier=voter_identifier,
                    award_category=award_category,
                    contact_id=contact_id
                )
                db.session.add(new_vote)
            
            # Handle question votes
            question = v.get('question')
            score = v.get('score')
            comments = v.get('comments')
            
            if question is not None and (score is not None or comments is not None):
                new_vote = Vote(
                    meeting_id=meeting_id,
                    voter_identifier=voter_identifier,
                    question=question,
                    score=score,
                    comments=comments
                )
                db.session.add(new_vote)
        
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing batch vote: {e}")
        return jsonify(success=False, message="An internal error occurred."), 500


@voting_bp.route('/voting/vote', methods=['POST'])
def vote_for_award():
    """Individual vote submission endpoint."""
    data = request.get_json()
    meeting_id = data.get('meeting_id')
    contact_id = data.get('contact_id')
    award_category = data.get('award_category')

    if not all([meeting_id, contact_id, award_category]):
        return jsonify(success=False, message="Missing data."), 400

    club_id = get_current_club_id()
    meeting_query = Meeting.query.filter_by(id=meeting_id)
    if club_id:
        meeting_query = meeting_query.filter(Meeting.club_id == club_id)
    meeting = meeting_query.first()
    if not meeting:
        return jsonify(success=False, message="Meeting not found."), 404
 
    is_admin = is_authorized(Permissions.MEETING_MANAGE)

    is_meeting_date = meeting.Meeting_Date == datetime.today().date()
    has_voting_view_results = is_authorized(Permissions.VOTING_VIEW_RESULTS, meeting=meeting)

    if not (meeting.status == 'running' or (meeting.status == 'finished' and is_admin) or (meeting.status != 'finished' and is_meeting_date and has_voting_view_results)):
        return jsonify(success=False, message="Voting is not active for this meeting."), 403

    # Check if category is disabled
    from .models.voting import MeetingAwardConfig
    config = MeetingAwardConfig.query.filter_by(meeting_id=meeting.id, award_category=award_category).first()
    if config and (config.max_votes_per_user == 0 or config.max_winners == 0):
        return jsonify(success=False, message="This award is not enabled for this meeting."), 400

    # Determine voter identity
    if current_user.is_authenticated:
        voter_identifier = f"user_{current_user.id}"
    else:
        if 'voter_token' not in session:
            session['voter_token'] = secrets.token_hex(16)
        voter_identifier = session['voter_token']
    
    # Check for an existing vote from this identifier for this category and contact
    existing_vote = Vote.query.filter_by(
        meeting_id=meeting_id,
        voter_identifier=voter_identifier,
        award_category=award_category,
        contact_id=contact_id
    ).first()

    your_vote_id = None

    try:
        if existing_vote:
            # User clicked the same person again, so cancel the vote
            db.session.delete(existing_vote)
            your_vote_id = None
        else:
            # New vote
            new_vote = Vote(
                meeting_id=meeting.id,
                voter_identifier=voter_identifier,
                award_category=award_category,
                contact_id=contact_id
            )
            db.session.add(new_vote)
            your_vote_id = contact_id

        db.session.commit()

        if meeting.status == 'finished' and is_admin:
            from .models.voting import MeetingAwardWinner
            MeetingAwardWinner.query.filter_by(meeting_id=meeting.id, award_category=award_category).delete()
            if your_vote_id:
                new_winner = MeetingAwardWinner(meeting_id=meeting.id, award_category=award_category, contact_id=your_vote_id)
                db.session.add(new_winner)
            db.session.commit()

        return jsonify(success=True, your_vote_id=your_vote_id, award_category=award_category)

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error processing vote: {e}")
        return jsonify(success=False, message="An internal error occurred."), 500


@voting_bp.route('/voting/nps', methods=['GET'])
@login_required
def voting_nps():
    """NPS bar chart page showing Net Promoter Scores for all meetings."""
    club_id = get_current_club_id()
    
    # Fetch all finished meetings
    query = Meeting.query.filter(Meeting.status == 'finished')
    if club_id:
        query = query.filter(Meeting.club_id == club_id)
    meetings = query.order_by(Meeting.Meeting_Number.asc()).all()
    
    # Prepare data for the chart
    meeting_ids = [m.id for m in meetings]
    meeting_numbers = [m.Meeting_Number for m in meetings]
    meeting_dates = [m.Meeting_Date.strftime('%Y-%m-%d') if m.Meeting_Date else '' for m in meetings]
    
    # Get all NPS votes for these meetings in one go to be efficient
    all_votes = db.session.query(Vote.meeting_id, Vote.score).filter(
        Vote.meeting_id.in_(meeting_ids),
        Vote.question == "How likely are you to recommend this meeting to a friend or colleague?",
        Vote.score.isnot(None),
        Vote.score > 0
    ).all()


    
    # Group votes by meeting
    votes_by_meeting = {}
    for mtg_id, score in all_votes:
        if mtg_id not in votes_by_meeting:
            votes_by_meeting[mtg_id] = []
        votes_by_meeting[mtg_id].append(score)
    
    # Calculate true NPS for each meeting
    full_data = []
    for m in meetings:
        scores = votes_by_meeting.get(m.id, [])
        if scores:
            total = len(scores)
            promoters = sum(1 for s in scores if s >= 9)
            detractors = sum(1 for s in scores if s >= 1 and s <= 6)
            nps = (promoters - detractors) / total * 100
            score = round(nps, 1)
            det_pct = round(detractors / total * 100, 1)
            count = total
        else:
            # Fallback for stored value (if no raw votes, we don't know detailed breakdown)
            score = m.nps if m.nps is not None else 0
            det_pct = 0
            count = 0
            
        full_data.append({
            'id': m.id,
            'number': m.Meeting_Number,
            'score': score,
            'det_pct': det_pct,
            'count': count,
            'date': m.Meeting_Date.strftime('%Y-%m-%d') if m.Meeting_Date else ''
        })
    
    # Find the first non-zero score index
    first_nonzero_idx = 0
    for i, data in enumerate(full_data):
        if data['score'] != 0 or data['count'] > 0:
            first_nonzero_idx = i
            break
            
    # Slice the data from the first non-zero meeting
    filtered_data = full_data[first_nonzero_idx:]
    
    meeting_ids = [d['id'] for d in filtered_data]
    meeting_numbers = [d['number'] for d in filtered_data]
    nps_scores = [d['score'] for d in filtered_data]
    detractor_percentages = [d['det_pct'] for d in filtered_data]
    vote_counts = [d['count'] for d in filtered_data]
    meeting_dates = [d['date'] for d in filtered_data]
    
    return render_template('voting_nps.html',
                           meeting_ids=meeting_ids,
                           meeting_numbers=meeting_numbers,
                           nps_scores=nps_scores,
                           detractor_percentages=detractor_percentages,
                           vote_counts=vote_counts,
                           meeting_dates=meeting_dates)


@voting_bp.route('/voting/nps/comments/<int:meeting_id>', methods=['GET'])
@login_required
def get_nps_comments(meeting_id):
    """Get NPS comments for a specific meeting."""
    club_id = get_current_club_id()
    
    # Verify the meeting exists and belongs to the current club
    meeting = Meeting.query.get_or_404(meeting_id)
    if meeting.club_id != club_id:
         return jsonify(success=False, message="Meeting not found"), 404
    
    if not meeting:
        return jsonify({'comments': [], 'meeting_date': ''})
    
    # Get all NPS-related comments for this meeting
    all_comments = db.session.query(Vote.score, Vote.comments).filter(
        Vote.meeting_id == meeting_id,
        Vote.question == "How likely are you to recommend this meeting to a friend or colleague?",
        Vote.comments.isnot(None),
        Vote.comments != ''
    ).all()
    
    # Also get general feedback comments
    general_comments = db.session.query(Vote.score, Vote.comments).filter(
        Vote.meeting_id == meeting_id,
        Vote.question == "More feedback/comments",
        Vote.comments.isnot(None),
        Vote.comments != ''
    ).all()
    
    all_comments = [c[1] for c in all_comments] + [c[1] for c in general_comments]
    meeting_date = meeting.Meeting_Date.strftime('%Y-%m-%d') if meeting.Meeting_Date else ''
    
    return jsonify({
        'comments': all_comments,
        'meeting_date': meeting_date
    })


@voting_bp.route('/voting/<int:meeting_id>/live_results', methods=['GET'])
@login_required
@authorized_club_required
def voting_live_results(meeting_id):
    """AJAX endpoint to get real-time vote totals for a running meeting."""
    meeting = Meeting.query.get_or_404(meeting_id)
    
    # Authorize: user must have VOTING_TRACK_PROGRESS permission for this meeting
    if not is_authorized(Permissions.VOTING_TRACK_PROGRESS, meeting=meeting):
        return jsonify(success=False, message="Permission denied."), 403

    # Get total votes received (unique voters)
    total_voters = db.session.query(func.count(distinct(Vote.voter_identifier)))\
        .filter(Vote.meeting_id == meeting_id)\
        .scalar() or 0

    # Get vote counts for award categories
    counts = db.session.query(Vote.contact_id, Vote.award_category, func.count(Vote.id)).filter(
        Vote.meeting_id == meeting_id,
        Vote.award_category.isnot(None)
    ).group_by(Vote.contact_id, Vote.award_category).all()
    
    vote_data = []
    for cid, cat, count in counts:
        if cid:
            vote_data.append({
                'contact_id': cid,
                'award_category': cat,
                'count': count
            })
            
    return jsonify(
        success=True,
        total_voters=total_voters,
        votes=vote_data
    )





