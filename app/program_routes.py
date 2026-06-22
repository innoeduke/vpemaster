"""Blueprint and routes for program templates and enrollments."""
import json
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, jsonify, abort, flash, redirect, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from . import db
from .auth.utils import is_authorized, club_permission_required
from .auth.permissions import Permissions
from .club_context import get_current_club_id, authorized_club_required
from .models import Program, ProgramTask, ProgramEnrollment, User, Contact, Planner
from .services.planner_service import planner_service as program_service

program_bp = Blueprint('program_bp', __name__)


@program_bp.before_request
@login_required
@authorized_club_required
def check_program_enabled():
    """Ensure programs feature is accessible only if Planner module is enabled and user has permissions."""
    from app.club_context import is_module_enabled
    if not is_module_enabled('Planner'):
        abort(404)
    # Most endpoints require at least PROGRAMS_SELF
    if not is_authorized(Permissions.PROGRAMS_SELF):
        abort(403)


# ============================================================================
# PAGE ROUTES
# ============================================================================

@program_bp.route('/programs')
@club_permission_required(Permissions.PROGRAMS_MANAGE)
def programs_admin():
    """Renders the program templates administration interface."""
    club_id = get_current_club_id()
    # Fetch active users for enrollment selector mapping
    from app.models import Contact, ContactClub
    contacts = Contact.query.join(ContactClub).filter(ContactClub.club_id == club_id, Contact.Type == 'Member').all()
    Contact.populate_users(contacts, club_id=club_id)
    members = [c for c in contacts if hasattr(c, '_user') and c._user]
    
    return render_template('programs.html', members=members, header_title="Manage Templates")


# ============================================================================
# API ROUTES - TEMPLATES (PROGRAMS & TASKS)
# ============================================================================

@program_bp.route('/api/programs', methods=['GET'])
def get_programs():
    """List program templates active in the current club or global."""
    club_id = get_current_club_id()
    programs = Program.query.filter(
        (Program.club_id == club_id) | (Program.club_id.is_(None)),
        Program.is_active == True
    ).order_by(Program.display_order, Program.id).all()
    
    result = []
    for p in programs:
        phases = []
        for t in sorted(p.tasks, key=lambda task: task.display_order):
            if t.phase_label and t.phase_label not in phases:
                phases.append(t.phase_label)
        result.append({
            'id': p.id,
            'name': p.name,
            'description': p.description,
            'is_active': p.is_active,
            'display_order': p.display_order,
            'club_id': p.club_id,
            'tasks_count': len(p.tasks),
            'phases': phases
        })
    return jsonify(result)


@program_bp.route('/api/programs', methods=['POST'])
@club_permission_required(Permissions.PROGRAMS_MANAGE)
def create_program():
    """Create a new program template."""
    club_id = get_current_club_id()
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify(success=False, message="Name is required"), 400
        
    program = Program(
        club_id=club_id,
        name=data['name'],
        description=data.get('description'),
        is_active=data.get('is_active', True),
        display_order=data.get('display_order', 0),
        created_by_id=current_user.id
    )
    db.session.add(program)
    db.session.commit()
    return jsonify(success=True, id=program.id), 201


@program_bp.route('/api/programs/<int:id>', methods=['PUT'])
@club_permission_required(Permissions.PROGRAMS_MANAGE)
def update_program(id):
    """Update a program template."""
    club_id = get_current_club_id()
    program = Program.query.filter(
        Program.id == id,
        (Program.club_id == club_id) | (Program.club_id.is_(None))
    ).first_or_404()
    
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify(success=False, message="Name is required"), 400
        
    program.name = data['name']
    program.description = data.get('description')
    program.is_active = data.get('is_active', True)
    if 'display_order' in data:
        program.display_order = data['display_order']
        
    db.session.commit()
    return jsonify(success=True)


@program_bp.route('/api/programs/<int:id>', methods=['DELETE'])
@club_permission_required(Permissions.PROGRAMS_MANAGE)
def delete_program(id):
    """Soft delete a program template."""
    club_id = get_current_club_id()
    program = Program.query.filter(
        Program.id == id,
        Program.club_id == club_id
    ).first_or_404()
    
    program.is_active = False
    db.session.commit()
    return jsonify(success=True)


@program_bp.route('/api/programs/<int:pid>/tasks', methods=['GET'])
def get_program_tasks(pid):
    """List tasks of a program template."""
    club_id = get_current_club_id()
    program = Program.query.filter(
        Program.id == pid,
        (Program.club_id == club_id) | (Program.club_id.is_(None))
    ).first_or_404()
    
    return jsonify([{
        'id': t.id,
        'program_id': t.program_id,
        'title': t.title,
        'description': t.description,
        'phase_label': t.phase_label,
        'display_order': t.display_order,
        'completion_type': t.completion_type,
        'completion_config': t.completion_config,
        'is_required': t.is_required
    } for t in program.tasks])


@program_bp.route('/api/programs/<int:pid>/tasks', methods=['POST'])
@club_permission_required(Permissions.PROGRAMS_MANAGE)
def create_program_task(pid):
    """Create a new task in a program template."""
    club_id = get_current_club_id()
    program = Program.query.filter(
        Program.id == pid,
        Program.club_id == club_id
    ).first_or_404()
    
    data = request.get_json()
    if not data or not data.get('title') or not data.get('completion_type'):
        return jsonify(success=False, message="Title and completion type are required"), 400
        
    task = ProgramTask(
        program_id=program.id,
        title=data['title'],
        description=data.get('description'),
        phase_label=data.get('phase_label'),
        display_order=data.get('display_order', 0),
        completion_type=data['completion_type'],
        completion_config=data.get('completion_config'),
        is_required=data.get('is_required', True)
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(success=True, id=task.id), 201


@program_bp.route('/api/programs/<int:pid>/tasks/<int:tid>', methods=['PUT'])
@club_permission_required(Permissions.PROGRAMS_MANAGE)
def update_program_task(pid, tid):
    """Update a task in a program template."""
    club_id = get_current_club_id()
    program = Program.query.filter(
        Program.id == pid,
        Program.club_id == club_id
    ).first_or_404()
    
    task = ProgramTask.query.filter_by(id=tid, program_id=program.id).first_or_404()
    data = request.get_json()
    if not data or not data.get('title') or not data.get('completion_type'):
        return jsonify(success=False, message="Title and completion type are required"), 400
        
    task.title = data['title']
    task.description = data.get('description')
    task.phase_label = data.get('phase_label')
    task.completion_type = data['completion_type']
    task.completion_config = data.get('completion_config')
    task.is_required = data.get('is_required', True)
    if 'display_order' in data:
        task.display_order = data['display_order']
        
    db.session.commit()
    return jsonify(success=True)


@program_bp.route('/api/programs/<int:pid>/tasks/reorder', methods=['POST'])
@club_permission_required(Permissions.PROGRAMS_MANAGE)
def reorder_program_tasks(pid):
    """Reorder multiple tasks within a program template."""
    club_id = get_current_club_id()
    program = Program.query.filter(
        Program.id == pid,
        Program.club_id == club_id
    ).first_or_404()
    
    data = request.get_json()
    if not data or not data.get('task_ids'):
        return jsonify(success=False, message="Task IDs are required"), 400
        
    task_ids = data['task_ids']
    for index, tid in enumerate(task_ids):
        task = ProgramTask.query.filter_by(id=tid, program_id=program.id).first()
        if task:
            task.display_order = index
            
    db.session.commit()
    return jsonify(success=True)


@program_bp.route('/api/programs/<int:pid>/tasks/<int:tid>', methods=['DELETE'])
@club_permission_required(Permissions.PROGRAMS_MANAGE)
def delete_program_task(pid, tid):
    """Delete a task from a program template."""
    club_id = get_current_club_id()
    program = Program.query.filter(
        Program.id == pid,
        Program.club_id == club_id
    ).first_or_404()
    
    task = ProgramTask.query.filter_by(id=tid, program_id=program.id).first_or_404()
    db.session.delete(task)
    db.session.commit()
    return jsonify(success=True)


# ============================================================================
# API ROUTES - ENROLLMENTS & INSTANCES
# ============================================================================

@program_bp.route('/api/program-enrollments', methods=['GET'])
def get_enrollments():
    """List all program enrollments visible to the current user."""
    club_id = get_current_club_id()
    
    if is_authorized(Permissions.PROGRAMS_MANAGE):
        enrollments = ProgramEnrollment.query.filter_by(club_id=club_id)\
            .options(
                joinedload(ProgramEnrollment.program),
                joinedload(ProgramEnrollment.mentee),
                joinedload(ProgramEnrollment.mentor),
                joinedload(ProgramEnrollment.mentor_contact)
            ).all()
    else:
        enrollments = ProgramEnrollment.query.filter(
            ProgramEnrollment.club_id == club_id,
            ((ProgramEnrollment.user_id == current_user.id) | (ProgramEnrollment.mentor_user_id == current_user.id))
        ).options(
            joinedload(ProgramEnrollment.program),
            joinedload(ProgramEnrollment.mentee),
            joinedload(ProgramEnrollment.mentor),
            joinedload(ProgramEnrollment.mentor_contact)
        ).all()
        
    return jsonify([{
        'id': e.id,
        'program': {
            'id': e.program.id,
            'name': e.program.name
        },
        'mentee': {
            'id': e.mentee.id,
            'username': e.mentee.username,
            'name': e.mentee.get_contact(club_id).Name if e.mentee.get_contact(club_id) else e.mentee.username
        },
        'mentor': {
            'id': e.mentor.id if e.mentor else None,
            'username': e.mentor.username if e.mentor else None,
            'name': e.mentor_contact.Name if e.mentor_contact else (e.mentor.get_contact(club_id).Name if e.mentor and e.mentor.get_contact(club_id) else None)
        },
        'status': e.status,
        'started_at': e.started_at.strftime('%Y-%m-%d') if e.started_at else None,
        'completed_at': e.completed_at.strftime('%Y-%m-%d') if e.completed_at else None,
        'notes': e.notes,
        'progress': program_service.progress(e)
    } for e in enrollments])


@program_bp.route('/api/program-enrollments', methods=['POST'])
@club_permission_required(Permissions.PROGRAMS_MANAGE)
def enroll_member():
    """Enroll a member in a program template."""
    club_id = get_current_club_id()
    data = request.get_json()
    if not data or not data.get('program_id') or not data.get('user_id'):
        return jsonify(success=False, message="Program ID and User ID are required"), 400
        
    program = Program.query.filter(
        Program.id == data['program_id'],
        (Program.club_id == club_id) | (Program.club_id.is_(None))
    ).first_or_404()
    
    user = User.query.get_or_404(data['user_id'])
    
    # Check for duplicate active/paused enrollment
    existing = ProgramEnrollment.query.filter_by(
        program_id=program.id,
        user_id=user.id,
        club_id=club_id
    ).first()
    if existing:
        return jsonify(success=False, message="User is already enrolled in this program."), 400
        
    mentor_user_id = data.get('mentor_user_id')
    mentor_contact_id = data.get('mentor_contact_id')
    
    try:
        enrollment = program_service.create_enrollment(
            program=program,
            user_id=user.id,
            club_id=club_id,
            mentor_user_id=mentor_user_id,
            mentor_contact_id=mentor_contact_id,
            notes=data.get('notes')
        )
        return jsonify(success=True, id=enrollment.id), 201
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@program_bp.route('/api/program-enrollments/<int:id>', methods=['PUT'])
def update_enrollment(id):
    """Update enrollment details (mentor assignment, status, notes)."""
    club_id = get_current_club_id()
    enrollment = ProgramEnrollment.query.filter_by(id=id, club_id=club_id).first_or_404()
    
    # Auth check: only admin or the assigned mentor can update
    is_admin = is_authorized(Permissions.PROGRAMS_MANAGE)
    is_mentor = enrollment.mentor_user_id == current_user.id
    
    if not (is_admin or is_mentor):
        abort(403)
        
    data = request.get_json()
    if not data:
        return jsonify(success=False, message="No data provided"), 400
        
    if is_admin:
        # Mentor fields are admin-only
        if 'mentor_user_id' in data:
            enrollment.mentor_user_id = data['mentor_user_id']
        if 'mentor_contact_id' in data:
            enrollment.mentor_contact_id = data['mentor_contact_id']
            
    # Status and Notes can be edited by mentor or admin
    if 'status' in data:
        old_status = enrollment.status
        new_status = data['status']
        if new_status in ('active', 'paused', 'completed', 'cancelled'):
            enrollment.status = new_status
            if new_status == 'completed' and old_status != 'completed':
                enrollment.completed_at = datetime.now(timezone.utc)
            elif new_status != 'completed':
                enrollment.completed_at = None
                
    if 'notes' in data:
        enrollment.notes = data['notes']
        
    db.session.commit()
    return jsonify(success=True)


@program_bp.route('/api/program-enrollments/<int:id>', methods=['GET'])
def get_enrollment_details(id):
    """Get detailed status and tasks of a single enrollment."""
    club_id = get_current_club_id()
    enrollment = ProgramEnrollment.query.filter_by(id=id, club_id=club_id)\
        .options(
            joinedload(ProgramEnrollment.program),
            joinedload(ProgramEnrollment.mentee),
            joinedload(ProgramEnrollment.mentor),
            joinedload(ProgramEnrollment.mentor_contact)
        ).first_or_404()
        
    # Visibility check
    if not (is_authorized(Permissions.PROGRAMS_MANAGE) or 
            enrollment.user_id == current_user.id or 
            enrollment.mentor_user_id == current_user.id):
        abort(403)
        
    # Trigger bulk refresh if active
    if enrollment.status == 'active':
        program_service.bulk_refresh(enrollment)
        
    # Fetch planner tasks
    planner_tasks = Planner.query.filter_by(enrollment_id=enrollment.id)\
        .options(joinedload(Planner.program_task), joinedload(Planner.completed_by))\
        .all()
        
    tasks_data = []
    for p in planner_tasks:
        t = p.program_task
        if not t:
            continue
        tasks_data.append({
            'planner_id': p.id,
            'task_id': t.id,
            'title': t.title,
            'description': t.description,
            'phase_label': t.phase_label,
            'completion_type': t.completion_type,
            'is_required': t.is_required,
            'status': p.status,
            'auto_completed': p.auto_completed,
            'completed_at': p.completed_at.strftime('%Y-%m-%d %H:%M:%S') if p.completed_at else None,
            'completed_by': p.completed_by.username if p.completed_by else None
        })
        
    # Sort tasks by phase/display order
    tasks_data.sort(key=lambda x: (x['phase_label'] or '', x['planner_id']))
    
    return jsonify({
        'id': enrollment.id,
        'program': {
            'id': enrollment.program.id,
            'name': enrollment.program.name,
            'description': enrollment.program.description
        },
        'mentee': {
            'id': enrollment.mentee.id,
            'username': enrollment.mentee.username,
            'name': enrollment.mentee.get_contact(club_id).Name if enrollment.mentee.get_contact(club_id) else enrollment.mentee.username
        },
        'mentor': {
            'id': enrollment.mentor.id if enrollment.mentor else None,
            'username': enrollment.mentor.username if enrollment.mentor else None,
            'name': enrollment.mentor_contact.Name if enrollment.mentor_contact else (enrollment.mentor.get_contact(club_id).Name if enrollment.mentor and enrollment.mentor.get_contact(club_id) else None)
        },
        'status': enrollment.status,
        'started_at': enrollment.started_at.strftime('%Y-%m-%d') if enrollment.started_at else None,
        'completed_at': enrollment.completed_at.strftime('%Y-%m-%d') if enrollment.completed_at else None,
        'notes': enrollment.notes,
        'progress': program_service.progress(enrollment),
        'tasks': tasks_data
    })


@program_bp.route('/api/program-enrollments/<int:id>/tasks/<int:planner_id>/toggle', methods=['POST'])
def toggle_enrollment_task(id, planner_id):
    """Toggle completion of a manual enrollment task."""
    club_id = get_current_club_id()
    enrollment = ProgramEnrollment.query.filter_by(id=id, club_id=club_id).first_or_404()
    
    # Visibility check: mentee, mentor, or admin
    if not (is_authorized(Permissions.PROGRAMS_MANAGE) or 
            enrollment.user_id == current_user.id or 
            enrollment.mentor_user_id == current_user.id):
        abort(403)
        
    planner_row = Planner.query.filter_by(id=planner_id, enrollment_id=enrollment.id).first_or_404()
    
    try:
        updated_row = program_service.toggle_task(planner_row.id, current_user)
        return jsonify({
            'success': True,
            'status': updated_row.status,
            'completed_at': updated_row.completed_at.strftime('%Y-%m-%d %H:%M:%S') if updated_row.completed_at else None,
            'completed_by': updated_row.completed_by.username if updated_row.completed_by else None,
            'progress': program_service.progress(enrollment)
        })
    except Exception as e:
        return jsonify(success=False, message=str(e)), 400
