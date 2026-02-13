# vpemaster/voting_routes.py

from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
from flask import Blueprint, render_template, request, session, jsonify, current_app, redirect, url_for
from .models import SessionLog, SessionType, Contact, Meeting, User, MeetingRole, Vote, AuthRole
from . import db
from datetime import datetime
import secrets
from sqlalchemy import func
from flask_login import current_user
from .club_context import get_current_club_id

from .services.role_service import RoleService
from .utils import (
    get_session_voter_identifier,
    get_current_user_info,
    get_meetings_by_status,
    consolidate_session_logs,
    group_roles_by_category
)

voting_bp = Blueprint('voting_bp', __name__)


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

    winner_ids = {}
    if selected_meeting.status == 'running':
        # For a running meeting, the "winner" is who the current user voted for
        voter_identifier = get_session_voter_identifier()
        
        if voter_identifier:
            user_votes = Vote.query.filter_by(
                meeting_id=selected_meeting.id,
                voter_identifier=voter_identifier
            ).all()
            winner_ids = {vote.award_category: vote.contact_id for vote in user_votes}

    elif selected_meeting.status == 'finished':
        # For a finished meeting, the final winners are stored in the meeting object
        winner_ids = {
            'speaker': selected_meeting.best_speaker_id,
            'evaluator': selected_meeting.best_evaluator_id,
            'table-topic': selected_meeting.best_table_topic_id,
            'role-taker': selected_meeting.best_role_taker_id,
        }

    # Vote counts for officers
    vote_counts = {}
    if is_authorized(Permissions.BOOKING_ASSIGN_ALL, meeting=selected_meeting) and selected_meeting and selected_meeting.status in ['running', 'finished']:
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
        role_data['award_type'] = award_category if owner_id and award_category and owner_id == winner_ids.get(award_category) else None
        role_data['award_category_open'] = bool(award_category and not winner_ids.get(award_category))
        
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
        'table-topic': 4
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
    user_vote_id = None
    if meeting.status == 'running' and voter_identifier:
        vote = Vote.query.filter_by(
            meeting_id=meeting_id,
            voter_identifier=voter_identifier,
            award_category='role-taker'
        ).first()
        if vote:
            user_vote_id = vote.contact_id
            
    best_role_taker_id = meeting.best_role_taker_id if meeting.status == 'finished' else None

    # Vote counts for role-takers (admins only)
    vote_counts = {}
    if is_authorized(Permissions.BOOKING_ASSIGN_ALL, meeting=meeting) and meeting.status in ['running', 'finished']:
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
        role_entry = {
            'role': combined_role_names,
            'icon': 'fa-users', # Generic icon for consolidated roles
            'session_id': first_role.get('session_log_id'), # Might be None
            'owner_id': contact_id,
            'owner_name': first_role.get('owner_name'),
            'owner_avatar_url': first_role.get('owner_avatar_url'),
            'award_category': 'role-taker',
            'award_category_open': bool(not (user_vote_id if meeting.status == 'running' else best_role_taker_id)),
            'award_type': 'role-taker' if (user_vote_id == contact_id if meeting.status == 'running' else best_role_taker_id == contact_id) else None,
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
    club_id = get_current_club_id()
    
    # Show active meetings in dropdown
    limit_past = None if is_authorized(Permissions.MEDIA_ACCESS) else 8
    upcoming_meetings, default_meeting_id = get_meetings_by_status(
        limit_past=limit_past, status_filter=['running', 'finished'],
        columns=[Meeting.id, Meeting.Meeting_Date, Meeting.status, Meeting.Meeting_Number])
 
    if not meeting_id:
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
        return context
 
    selected_meeting = Meeting.query.get(meeting_id)
    if not selected_meeting or (club_id and selected_meeting.club_id != club_id):
        return context

    user, current_user_contact_id = get_current_user_info()
    context['current_user_contact_id'] = current_user_contact_id

    # Check if user has voted for this meeting
    voter_identifier = get_session_voter_identifier()
    if voter_identifier:
        vote_exists = Vote.query.filter_by(meeting_id=meeting_id, voter_identifier=voter_identifier).first()
        if vote_exists:
            context['has_voted'] = True
    
    # Access control for unpublished meetings
    contact = current_user.get_contact(club_id) if current_user.is_authenticated else None
    is_manager = (contact and contact.id == selected_meeting.manager_id) if selected_meeting else False
    
    # 1. Guests can ONLY access 'running' meetings
    is_guest = not current_user.is_authenticated or \
               (hasattr(current_user, 'primary_role_name') and current_user.primary_role_name == 'Guest')
    
    if is_guest:
        if selected_meeting.status == 'unpublished':
            return {
                'redirect': url_for('agenda_bp.meeting_notice', meeting_id=meeting_id)
            }
        elif selected_meeting.status != 'running':
            context['force_not_started'] = True
            context['selected_meeting'] = selected_meeting
            context['roles'] = [] # Prevent data leakage
            return context

    if selected_meeting and selected_meeting.status == 'unpublished' and not (is_authorized(Permissions.VOTING_VIEW_RESULTS, meeting=selected_meeting)):
        return {
            'redirect': url_for('agenda_bp.meeting_notice', meeting_id=meeting_id)
        }

    context['selected_meeting'] = selected_meeting
    
    # Permission checks
    # is_admin_view controls seeing results/accordion (Admin, Officer, VPE, Manager)
    context['is_admin_view'] = is_authorized(Permissions.VOTING_VIEW_RESULTS, meeting=selected_meeting)
    
    # can_track_progress controls seeing results WHILE running (Admin only)
    context['can_track_progress'] = is_authorized(Permissions.VOTING_TRACK_PROGRESS, meeting=selected_meeting)

    roles = _get_roles_for_voting(meeting_id, selected_meeting)
    context['roles'] = roles
    context['sorted_role_groups'] = group_roles_by_category(roles)
    context['best_award_ids'] = selected_meeting.get_best_award_ids() if selected_meeting else set()

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
def voting(meeting_id):
    """Main voting page route."""
    context = _get_voting_page_context(meeting_id)
    
    # Handle redirects from context
    if isinstance(context, dict) and 'redirect' in context:
        return redirect(context['redirect'])
    
    # Access Control Logic
    meeting = context.get('selected_meeting')
    if meeting:
        if meeting.status == 'finished':
            # Finished meetings: Only users with VOTING_VIEW_RESULTS can see results
            # Others (guests and regular users) should not access this page
            if not is_authorized(Permissions.VOTING_VIEW_RESULTS):
                return redirect(url_for('agenda_bp.agenda'))
                 
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

    if meeting.status != 'running':
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

    is_admin = is_authorized(Permissions.BOOKING_ASSIGN_ALL)

    if not (meeting.status == 'running' or (meeting.status == 'finished' and is_admin)):
        return jsonify(success=False, message="Voting is not active for this meeting."), 403

    # Determine voter identity
    if current_user.is_authenticated:
        voter_identifier = f"user_{current_user.id}"
    else:
        if 'voter_token' not in session:
            session['voter_token'] = secrets.token_hex(16)
        voter_identifier = session['voter_token']
    
    # Check for an existing vote from this identifier for this category
    existing_vote = Vote.query.filter_by(
        meeting_id=meeting_id,
        voter_identifier=voter_identifier,
        award_category=award_category
    ).first()

    your_vote_id = None

    try:
        if existing_vote:
            if existing_vote.contact_id == contact_id:
                # User clicked the same person again, so cancel the vote
                db.session.delete(existing_vote)
                your_vote_id = None
            else:
                # User is changing their vote to a new person
                existing_vote.contact_id = contact_id
                your_vote_id = contact_id
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
            if award_category == 'speaker':
                meeting.best_speaker_id = your_vote_id
            elif award_category == 'evaluator':
                meeting.best_evaluator_id = your_vote_id
            elif award_category == 'table-topic':
                meeting.best_table_topic_id = your_vote_id
            elif award_category == 'role-taker':
                meeting.best_role_taker_id = your_vote_id
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
    
    all_comments = [c[0] for c in all_comments] + [c[0] for c in general_comments]
    meeting_date = meeting.Meeting_Date.strftime('%Y-%m-%d') if meeting.Meeting_Date else ''
    
    return jsonify({
        'comments': all_comments,
        'meeting_date': meeting_date
    })





