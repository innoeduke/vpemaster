# vpemaster/voting_routes.py

from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
from flask import Blueprint, render_template, request, session, jsonify, current_app, redirect, url_for
from .models import SessionLog, SessionType, Contact, Meeting, User, MeetingRole, Vote, AuthRole
from . import db
from datetime import datetime
import secrets
from sqlalchemy import func, distinct
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


def _enrich_role_data_for_voting(roles_dict, selected_meeting):
    """
    Enriches role data with voting-specific information (awards, vote counts).
    
    Args:
        roles_dict: Dictionary of consolidated roles
        selected_meeting: Meeting object
    
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
            user_votes = Vote.query.filter_by(
                meeting_id=selected_meeting.id,
                voter_identifier=voter_identifier
            ).all()
            for vote in user_votes:
                if vote.award_category:
                    winner_set.add((vote.award_category, vote.contact_id))

    elif selected_meeting.status == 'finished':
        from .models.voting import MeetingAwardWinner
        winners = MeetingAwardWinner.query.filter_by(meeting_id=selected_meeting.id).all()
        if winners:
            for w in winners:
                winner_set.add((w.award_category, w.contact_id))
        else:
            if selected_meeting.best_speaker_id: winner_set.add(('speaker', selected_meeting.best_speaker_id))
            if selected_meeting.best_evaluator_id: winner_set.add(('evaluator', selected_meeting.best_evaluator_id))
            if selected_meeting.best_table_topic_id: winner_set.add(('table-topic', selected_meeting.best_table_topic_id))
            if selected_meeting.best_role_taker_id: winner_set.add(('role-taker', selected_meeting.best_role_taker_id))
            if selected_meeting.best_debater_id: winner_set.add(('debater', selected_meeting.best_debater_id))

    # Vote counts for officers
    vote_counts = {}
    if (is_authorized(Permissions.MEETING_MANAGE, meeting=selected_meeting) or is_authorized(Permissions.VOTING_TRACK_PROGRESS, meeting=selected_meeting)) and selected_meeting and selected_meeting.status in ['running', 'finished']:
        counts = db.session.query(Vote.contact_id, Vote.award_category, func.count(Vote.id)).filter(
            Vote.meeting_id == selected_meeting.id
        ).group_by(Vote.contact_id, Vote.award_category).all()
        
        for cid, cat, count in counts:
            vote_counts[(cid, cat)] = count

    enriched_roles = []
    for _, role_data in roles_dict.items():
        role_obj = role_data.get('role_obj')
        if not role_obj:
            role_obj = MeetingRole.query.filter_by(name=role_data['role']).first()

        role_data['icon'] = role_obj.icon if role_obj and role_obj.icon else "fa-question-circle"
        role_data['session_id'] = role_data['session_ids'][0]

        owner_id = role_data['owner_id']
        award_category = role_obj.award_category if role_obj else None

        if role_obj and role_obj.name == 'Keynote Speaker':
            from .constants import ProjectID
            # Check the first session log for project details
            # Note: 'logs' key is removed in consolidate_roles, must fetch by ID
            session_ids = role_data.get('session_ids')
            first_log = db.session.get(SessionLog, session_ids[0]) if session_ids else None
            
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
        return CATEGORY_ORDER.get(cat, 99)

    roles.sort(key=lambda x: (
        get_category_priority(x),
        x.get('award_category', '') or '', 
        x['role']
    ))
    
    return roles


def _get_roles_for_voting(meeting_id, meeting):
    """
    Helper function to get and process roles for the voting page.
    
    Args:
        meeting_id: Meeting ID
        meeting: Meeting object
    
    Returns:
        list: Processed roles for voting
    """
    if not meeting:
        return []
        
    # Fetch roles and enrich them
    club_id = meeting.club_id
    # Re-fetch logs for consolidation to be safe if RoleService doesn't provide enough info
    all_logs = SessionLog.query.filter_by(meeting_id=meeting_id).all()
    consolidated = consolidate_session_logs(all_logs)
    
    enriched_roles = _enrich_role_data_for_voting(consolidated, meeting)
    
    # Consolidate 'role-taker' category to one row per person
    # 1. Separate role-takers from others
    other_roles = [r for r in enriched_roles if r.get('award_category') != 'role-taker']
    
    # 2. Get all role takers for the meeting using RoleService
    role_takers_map = RoleService.get_role_takers(meeting_id, meeting.club_id)
    
    # 3. Create consolidated rows for each person who took a 'role-taker' role
    consolidated_role_takers = []
    
    # Determine winner info for role-taker award
    voter_identifier = get_session_voter_identifier()
    user_vote_ids = set()
    if meeting.status == 'running' and voter_identifier:
        votes = Vote.query.filter_by(
            meeting_id=meeting_id,
            voter_identifier=voter_identifier,
            award_category='role-taker'
        ).all()
        for vote in votes:
            if vote.contact_id:
                user_vote_ids.add(vote.contact_id)
            
    role_taker_winner_ids = set()
    if meeting.status == 'finished':
        from .models.voting import MeetingAwardWinner
        winners = MeetingAwardWinner.query.filter_by(meeting_id=meeting.id, award_category='role-taker').all()
        if winners:
            role_taker_winner_ids = {w.contact_id for w in winners}
        elif meeting.best_role_taker_id:
            role_taker_winner_ids.add(meeting.best_role_taker_id)

    # Vote counts for role-takers (admins only)
    vote_counts = {}
    if (is_authorized(Permissions.MEETING_MANAGE, meeting=meeting) or is_authorized(Permissions.VOTING_TRACK_PROGRESS, meeting=meeting)) and meeting.status in ['running', 'finished']:
        counts = db.session.query(Vote.contact_id, func.count(Vote.id)).filter(
            Vote.meeting_id == meeting_id,
            Vote.award_category == 'role-taker'
        ).group_by(Vote.contact_id).all()
        for cid, count in counts:
            vote_counts[cid] = count

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
            'vote_count': vote_counts.get(contact_id, 0)
        }
        consolidated_role_takers.append(role_entry)

    # Combine back
    final_roles = other_roles + consolidated_role_takers
    
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
    club_id = get_current_club_id()
    
    # Show active meetings in dropdown
    limit_past = None if is_authorized(Permissions.MEDIA_MANAGE) else 8
    upcoming_meetings, default_meeting_id = get_meetings_by_status(
        limit_past=limit_past, status_filter=['unpublished', 'not started', 'running', 'finished'],
        columns=[Meeting.id, Meeting.Meeting_Date, Meeting.status, Meeting.Meeting_Number])
 
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
 
    selected_meeting = Meeting.query.get(meeting_id)
    if not selected_meeting or (club_id and selected_meeting.club_id != club_id):
        return context

    context['db_status'] = selected_meeting.status
    context['can_edit_meeting_status'] = is_authorized(Permissions.MEETING_MANAGE, meeting=selected_meeting)

    # Check if we should override status for display and bypass notices
    is_meeting_date = selected_meeting.Meeting_Date == datetime.today().date()
    has_voting_view_results = is_authorized(Permissions.VOTING_VIEW_RESULTS, meeting=selected_meeting)
    
    if is_meeting_date and has_voting_view_results:
        # Eager load the relation to avoid DetachedInstanceError
        _ = selected_meeting.award_winners
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
    if voter_identifier:
        vote_exists = Vote.query.filter_by(meeting_id=meeting_id, voter_identifier=voter_identifier).first()
        if vote_exists:
            context['has_voted'] = True
    
    context['selected_meeting'] = selected_meeting
    
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

    roles = _get_roles_for_voting(meeting_id, selected_meeting)
    context['roles'] = roles
    context['sorted_role_groups'] = group_roles_by_category(roles)
    context['best_award_ids'] = selected_meeting.get_best_award_ids() if selected_meeting else set()

    # Fetch award configs
    context['award_configs'] = {}
    if selected_meeting:
        from app.models.voting import MeetingAwardConfig
        configs = MeetingAwardConfig.query.filter_by(meeting_id=meeting_id).all()
        for config in configs:
            context['award_configs'][config.award_category] = {
                'max_votes': config.max_votes_per_user,
                'max_winners': config.max_winners
            }

    # Fetch existing meeting rating
    context['meeting_rating_score'] = None
    if voter_identifier:
        rating_vote = Vote.query.filter_by(
            meeting_id=meeting_id,
            voter_identifier=voter_identifier,
            question="How likely are you to recommend this meeting to a friend or colleague?"
        ).first()
        if rating_vote:
            context['meeting_rating_score'] = rating_vote.score

    # Fetch existing meeting feedback
    context['meeting_feedback_comment'] = ""
    if voter_identifier:
        feedback_vote = Vote.query.filter_by(
            meeting_id=meeting_id,
            voter_identifier=voter_identifier,
            question="More feedback/comments"
        ).first()
        if feedback_vote:
            context['meeting_feedback_comment'] = feedback_vote.comments

    return context


@voting_bp.route('/voting', defaults={'meeting_id': None}, methods=['GET'])
@voting_bp.route('/voting/<int:meeting_id>', methods=['GET'])
@authorized_club_required
def voting(meeting_id):
    """Main voting page route."""
    context = _get_voting_page_context(meeting_id)
    
    # Handle notice context from dictionary returns
    if isinstance(context, dict) and 'notice_image' in context:
        return render_template('voting.html', **context)
                 
    return render_template('voting.html', **context)


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
        
        # Add new votes
        for v in votes:
            contact_id = v.get('contact_id')
            award_category = v.get('award_category')
            if contact_id and award_category:
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





