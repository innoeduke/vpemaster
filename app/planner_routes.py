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
    plans = Planner.query.filter_by(user_id=current_user.id, club_id=club_id).order_by(Planner.meeting_number).all()
    
    # 2. Fetch unpublished meetings for the dropdown
    unpublished_meetings = Meeting.query.filter_by(club_id=club_id, status='unpublished').order_by(Meeting.Meeting_Number).all()
    
    # 3. Fetch projects grouped by level
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
                         grouped_projects=grouped_projects,
                         header_title="Planner")

@planner_bp.route('/api/meeting/<int:meeting_number>')
@login_required
def get_meeting_info(meeting_number):
    club_id = get_current_club_id()
    meeting = Meeting.query.filter_by(club_id=club_id, Meeting_Number=meeting_number).first_or_404()
    
    # Use RoleService to get consolidated roles for this meeting
    from .services.role_service import RoleService
    meeting_roles = RoleService.get_meeting_roles(meeting_number, club_id)
    
    unique_roles = {}
    for r in meeting_roles:
        # Exclude permanent officer roles (VPE, VPM, etc.)
        if r.get('type') == 'officer':
            continue
            
        role_id = r['role_id']
        role_name = r['role']
        
        if role_id not in unique_roles:
            session_title = r.get('session_title')
            unique_roles[role_id] = {
                'id': role_id,
                'name': role_name,
                'valid_for_project': r.get('valid_for_project', False),
                'session_title': session_title,
                'expected_format': RoleService.get_expected_format_for_session(session_title),
                'session_id': r.get('session_id'),
                'is_available': not r.get('owner_id')
            }
        elif unique_roles[role_id]['is_available'] == False and not r.get('owner_id'):
            # Prioritize available slots for booking
            unique_roles[role_id]['session_id'] = r.get('session_id')
            unique_roles[role_id]['is_available'] = True
    
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
        meeting_number=data.get('meeting_number'),
        meeting_role_id=data.get('meeting_role_id'),
        project_id=data.get('project_id'),
        status=data.get('status', 'draft'), # Use status if provided
        notes=data.get('notes'),
        user_id=current_user.id,
        club_id=club_id
    )
    
    db.session.add(new_plan)
    db.session.commit()
    
    return jsonify({'id': new_plan.id, 'message': 'Plan created successfully'}), 201

@planner_bp.route('/api/planner/<int:plan_id>', methods=['PUT'])
@login_required
def update_plan(plan_id):
    plan = Planner.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    data = request.get_json()
    
    if 'meeting_number' in data:
        plan.meeting_number = data['meeting_number']
    if 'meeting_role_id' in data:
        plan.meeting_role_id = data['meeting_role_id']
    if 'project_id' in data:
        plan.project_id = data['project_id']
    if 'notes' in data:
        plan.notes = data['notes']
    if 'status' in data:
        plan.status = data['status']
    
    db.session.commit()
    return jsonify({'message': 'Plan updated successfully'})

@planner_bp.route('/api/planner/<int:plan_id>/cancel', methods=['POST'])
@login_required
def cancel_plan(plan_id):
    plan = Planner.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    
    # 1. Update status to cancelled
    plan.status = 'cancelled'
    
    # 2. If it was booked/waitlisted, remove from meeting
    if plan.meeting_number and plan.meeting_role_id:
        # Find the session log for this meeting and role
        session_log = SessionLog.query.join(SessionType).filter(
            SessionLog.Meeting_Number == plan.meeting_number,
            SessionType.role_id == plan.meeting_role_id
        ).first()
        
        if session_log:
            user_contact_id = current_user.contact_id
            if user_contact_id:
                RoleService.cancel_meeting_role(session_log, user_contact_id, is_admin=True) # is_admin=True to skip ownership check if necessary, though it should be fine
    
    db.session.commit()
    return jsonify({'message': 'Plan cancelled successfully'})

@planner_bp.route('/api/planner/<int:plan_id>', methods=['DELETE'])
@login_required
def delete_plan(plan_id):
    plan = Planner.query.filter_by(id=plan_id, user_id=current_user.id).first_or_404()
    db.session.delete(plan)
    db.session.commit()
    return jsonify({'message': 'Plan deleted successfully'})
