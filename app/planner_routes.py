from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import current_user, login_required
from .models import db, Planner, MeetingRole, Project, Club, Meeting, SessionType, SessionLog
from .auth.permissions import Permissions, permission_required
from .club_context import get_current_club_id
from datetime import datetime
from .constants import ProjectID
from .services.role_service import RoleService

planner_bp = Blueprint('planner_bp', __name__)

@planner_bp.route('/planner')
@login_required
def planner():
    club_id = get_current_club_id()
    
    # 1. Fetch user's plans
    plans = Planner.query.filter_by(user_id=current_user.id, club_id=club_id).order_by(Planner.meeting_id).all()
    
    # 2. Fetch all terms for the club to show in the filter
    from .utils import get_terms, get_active_term, get_date_ranges_for_terms
    terms = get_terms()
    
    # 3. Determine selected terms (support multi-select like contacts page)
    selected_term_ids = request.args.getlist('term')
    
    # Fallback: if no term selected, use the active term
    current_term = get_active_term(terms)
    if not selected_term_ids:
        if current_term:
            selected_term_ids = [current_term['id']]
        elif terms:
            selected_term_ids = [terms[0]['id']]
            
    # 4. Fetch unpublished meetings filtered by term date ranges
    from sqlalchemy import or_
    date_ranges = get_date_ranges_for_terms(selected_term_ids, terms)
    
    query = Meeting.query.filter_by(club_id=club_id, status='unpublished')
    if date_ranges:
        conditions = [Meeting.Meeting_Date.between(start, end) for start, end in date_ranges]
        query = query.filter(or_(*conditions))
    
    unpublished_meetings = query.order_by(Meeting.Meeting_Date.asc(), Meeting.id.asc()).all()
    
    # 5. Fetch projects grouped by level
    contact = current_user.get_contact(club_id)
    projects_by_level = {}
    if contact:
        projects = contact.get_pathway_projects_with_status()
        for p in projects:
            level = p.level or 1
            if level not in projects_by_level:
                projects_by_level[level] = []
            projects_by_level[level].append(p)
            
    # Sort levels and create grouped list for template
    sorted_levels = sorted(projects_by_level.keys())
    grouped_projects = [(level, projects_by_level[level]) for level in sorted_levels]

    return render_template('planner.html', 
                         plans=plans, 
                         meetings=unpublished_meetings,
                         terms=terms,
                         selected_term_ids=selected_term_ids,
                         grouped_projects=grouped_projects,
                         header_title="Planner")

@planner_bp.route('/api/meeting/<int:meeting_id>')
@login_required
def get_meeting_info(meeting_id):
    club_id = get_current_club_id()
    meeting = Meeting.query.get_or_404(meeting_id)
    if club_id and meeting.club_id != club_id:
         return jsonify(success=False, message="Meeting not found"), 404
    
    # Use RoleService to get consolidated roles for this meeting
    from .services.role_service import RoleService
    meeting_roles = RoleService.get_meeting_roles(meeting_id, club_id)
    
    unique_roles = {}
    for r in meeting_roles:
        # Exclude permanent officer roles (VPE, VPM, etc.)
        if r.get('type') == 'officer':
            continue
            
        role_id = r['role_id']
        role_name = r['role']
        
        # Calculate current participant count (owner + waitlist) for this slot
        owner_id = r.get('owner_id')
        waitlist_count = len(r.get('waitlist', []))
        score = (1 if owner_id else 0) + waitlist_count
        
        if role_id not in unique_roles:
            session_title = r.get('session_title')
            unique_roles[role_id] = {
                'id': role_id,
                'name': role_name,
                'valid_for_project': r.get('valid_for_project', False),
                'session_title': session_title,
                'expected_format': RoleService.get_expected_format_for_session(session_title),
                'session_id': r.get('session_id'),
                'is_available': not owner_id,
                'score': score
            }
        else:
            # For roles allow multiple entries (has_single_owner=True),
            # select the entry with the least count of owners + waitlists.
            if r.get('has_single_owner'):
                current_best = unique_roles[role_id]
                if score < current_best['score']:
                    unique_roles[role_id].update({
                        'session_id': r.get('session_id'),
                        'is_available': not owner_id,
                        'score': score
                    })
                elif score == current_best['score']:
                    # Tie-breaker: prioritize slots without an owner (avoids jumping behind an existing booking)
                    if not owner_id and not unique_roles[role_id]['is_available']:
                        unique_roles[role_id].update({
                            'session_id': r.get('session_id'),
                            'is_available': True,
                            'score': score
                        })
    
    # Sort roles by name alphabetically
    sorted_roles = sorted(unique_roles.values(), key=lambda x: x['name'])
    
    return jsonify({
        'date': meeting.Meeting_Date.strftime('%Y-%m-%d') if meeting.Meeting_Date else 'N/A',
        'roles': sorted_roles
    })

@planner_bp.route('/api/planner', methods=['POST'])
@login_required
def create_plan():
    data = request.get_json()
    club_id = get_current_club_id()
    
    new_plan = Planner(
        meeting_id=data.get('meeting_id'),
        meeting_number=data.get('meeting_number'), # Keep for backward compat/display if needed
        meeting_role_id=data.get('meeting_role_id'),
        project_id=data.get('project_id'),
        status=data.get('status', 'draft'), # Use status if provided
        notes=data.get('notes'),
        user_id=current_user.id,
        club_id=club_id
    )
    
    db.session.add(new_plan)
    db.session.commit()
    
    # Invalidate booking page cache for this meeting
    if new_plan.meeting_id:
        RoleService._clear_meeting_cache(new_plan.meeting_id, club_id)
    
    return jsonify({'id': new_plan.id, 'message': 'Plan created successfully'}), 201

@planner_bp.route('/api/planner/<int:plan_id>', methods=['PUT'])
@login_required
def update_plan(plan_id):
    plan = Planner.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    
    if 'meeting_id' in data:
        plan.meeting_id = data['meeting_id']
        meeting = Meeting.query.get(plan.meeting_id)
        if meeting:
            plan.meeting_number = meeting.Meeting_Number
    if 'meeting_role_id' in data:
        plan.meeting_role_id = data['meeting_role_id']
    if 'project_id' in data:
        plan.project_id = data['project_id']
    if 'notes' in data:
        plan.notes = data['notes']
    if 'status' in data:
        plan.status = data['status']
    
    db.session.commit()

    # Invalidate booking page cache for this meeting
    if plan.meeting_id:
        club_id = get_current_club_id()
        RoleService._clear_meeting_cache(plan.meeting_id, club_id)

    return jsonify({'message': 'Plan updated successfully'})

@planner_bp.route('/api/planner/<int:plan_id>/cancel', methods=['POST'])
@login_required
def cancel_plan(plan_id):
    plan = Planner.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    
    # 1. Update status to cancelled
    plan.status = 'cancelled'
    
    # 2. If it was booked/waitlisted, remove from meeting
    if plan.meeting_id and plan.meeting_role_id:
        # Find the session log for this meeting and role
        session_log = SessionLog.query.join(SessionType).filter(
            SessionLog.meeting_id == plan.meeting_id,
            SessionType.role_id == plan.meeting_role_id
        ).first()
        
        if session_log:
            user_contact_id = current_user.contact_id
            if user_contact_id:
                RoleService.cancel_meeting_role(session_log, user_contact_id, is_admin=True) # is_admin=True to skip ownership check if necessary, though it should be fine
    
    db.session.commit()

    # Invalidate booking page cache for this meeting
    if plan.meeting_id:
        club_id = get_current_club_id()
        RoleService._clear_meeting_cache(plan.meeting_id, club_id)

    return jsonify({'message': 'Plan cancelled successfully'})

@planner_bp.route('/api/planner/<int:plan_id>', methods=['DELETE'])
@login_required
def delete_plan(plan_id):
    plan = Planner.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    meeting_id = plan.meeting_id
    db.session.delete(plan)
    db.session.commit()

    # Invalidate booking page cache for this meeting
    if meeting_id:
        club_id = get_current_club_id()
        RoleService._clear_meeting_cache(meeting_id, club_id)

    return jsonify({'message': 'Plan deleted successfully'})
