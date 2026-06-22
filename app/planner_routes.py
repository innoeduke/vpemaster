from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import current_user, login_required
from .models import db, Planner, MeetingRole, Project, Club, Meeting, SessionType, SessionLog, Program, ProgramTask, ProgramEnrollment, Contact, ContactClub
from .auth.permissions import Permissions
from .auth.utils import is_authorized
from .club_context import get_current_club_id
from sqlalchemy.orm import joinedload
from datetime import datetime
import calendar as _cal
import re as _re
from .constants import ProjectID
from .services.role_service import RoleService
from .services.planner_service import planner_service

planner_bp = Blueprint('planner_bp', __name__)

_MONTH_NAMES_EN = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def _format_month_label(iso_date, locale, compact=False):
    """Render a YYYY-MM-DD (or YYYY-MM) string as 'Mon YYYY' for the toggle button."""
    if not iso_date:
        return ''
    m = _re.match(r'^(\d{4})-(\d{2})', str(iso_date))
    if not m:
        return str(iso_date)
    year, month = int(m.group(1)), int(m.group(2))
    if locale == 'zh_CN':
        if compact:
            return f'{year % 100}年{month}月'
        return f'{year}年{month}月'
    if compact:
        return f"{_MONTH_NAMES_EN[month]} '{str(year)[-2:]}"
    return f'{_MONTH_NAMES_EN[month]} {year}'

@planner_bp.before_request
def check_planner_enabled():
    from app.club_context import is_module_enabled
    from app.auth.utils import is_authorized
    from flask import abort
    if not is_module_enabled('Planner'):
        abort(404)
    if not is_authorized(Permissions.PROGRAMS_SELF):
        abort(403)


@planner_bp.route('/planner')
@login_required
def planner():
    club_id = get_current_club_id()
    
    # 1. Fetch user's standalone plans (no enrollment links) with joined relationships
    from sqlalchemy.orm import joinedload
    plans = Planner.query.filter_by(user_id=current_user.id, club_id=club_id)\
        .filter(Planner.enrollment_id.is_(None))\
        .options(joinedload(Planner.meeting), joinedload(Planner.role), joinedload(Planner.project))\
        .order_by(Planner.meeting_id).all()
        
    # Fetch program enrollments based on view mode
    view_mode = request.args.get('view', 'mine')
    if view_mode == 'all' and not is_authorized(Permissions.PROGRAMS_MANAGE):
        view_mode = 'mine'
        
    if view_mode == 'all':
        enrollments = ProgramEnrollment.query.filter_by(club_id=club_id)\
            .options(
                joinedload(ProgramEnrollment.program),
                joinedload(ProgramEnrollment.mentee),
                joinedload(ProgramEnrollment.mentor),
                joinedload(ProgramEnrollment.mentor_contact)
            ).all()
    elif view_mode == 'mentor':
        enrollments = ProgramEnrollment.query.filter_by(club_id=club_id, mentor_user_id=current_user.id)\
            .options(
                joinedload(ProgramEnrollment.program),
                joinedload(ProgramEnrollment.mentee),
                joinedload(ProgramEnrollment.mentor),
                joinedload(ProgramEnrollment.mentor_contact)
            ).all()
    else: # 'mine'
        enrollments = ProgramEnrollment.query.filter_by(club_id=club_id, user_id=current_user.id)\
            .options(
                joinedload(ProgramEnrollment.program),
                joinedload(ProgramEnrollment.mentee),
                joinedload(ProgramEnrollment.mentor),
                joinedload(ProgramEnrollment.mentor_contact)
            ).all()

    # Bulk refresh active enrollments and compute progress stats
    for e in enrollments:
        if e.status == 'active':
            planner_service.bulk_refresh(e)
        e.progress_stats = planner_service.progress(e)
    
    # 2. Fetch all terms for the club to show in the filter
    from .utils import get_terms, get_active_term, get_date_ranges_for_terms
    terms = get_terms()

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    start_month = request.args.get('start_month')
    end_month = request.args.get('end_month')

    if start_month and _re.match(r'^\d{4}-\d{2}$', start_month):
        start_date = f'{start_month}-01'
    if end_month and _re.match(r'^\d{4}-\d{2}$', end_month):
        last_day = _cal.monthrange(int(end_month[:4]), int(end_month[5:7]))[1]
        end_date = f'{end_month}-{last_day:02d}'

    # Fallback: if no dates selected, use the active term
    current_term = get_active_term(terms)
    if not start_date and not end_date:
        if current_term:
            start_date = current_term['start']
            end_date = current_term['end']

    # Derive start_month / end_month for the modal pre-fill (from the resolved dates)
    def _to_month(iso_date):
        if not iso_date:
            return ''
        m = _re.match(r'^(\d{4})-(\d{2})', str(iso_date))
        return f'{m.group(1)}-{m.group(2)}' if m else ''

    if not start_month:
        start_month = _to_month(start_date)
    if not end_month:
        end_month = _to_month(end_date)

    # 4. Fetch future published meetings filtered by date ranges
    from sqlalchemy import or_, func
    date_ranges = []
    if start_date and end_date:
        date_ranges = [(start_date, end_date)]

    query = Meeting.query.filter(
        Meeting.club_id == club_id,
        Meeting.status != 'unpublished',
        Meeting.status != 'finished',
        Meeting.Meeting_Date >= func.current_date()
    )
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

    from .utils import get_dropdown_metadata
    dropdown_data = get_dropdown_metadata()

    from app.translations.translations import get_locale as _gl
    _locale = _gl()
    range_label = ''
    if start_date and end_date:
        range_label = f'{_format_month_label(start_date, _locale, compact=True)} — {_format_month_label(end_date, _locale, compact=True)}'

    # Fetch active programs for new enrollment picker
    active_programs = Program.query.filter(
        (Program.club_id == club_id) | (Program.club_id.is_(None)),
        Program.is_active == True
    ).order_by(Program.display_order, Program.id).all()

    # Fetch contacts for mentor selection
    contacts = Contact.query.join(ContactClub).filter(ContactClub.club_id == club_id, Contact.Type == 'Member').order_by(Contact.Name).all()
    Contact.populate_users(contacts, club_id=club_id)

    return render_template('planner.html',
                         plans=plans,
                         enrollments=enrollments,
                         view_mode=view_mode,
                         active_programs=active_programs,
                         contacts=contacts,
                         is_admin=is_authorized(Permissions.PROGRAMS_MANAGE),
                         can_manage_members=is_authorized(Permissions.MEMBERS_MANAGE),
                         meetings=unpublished_meetings,
                         terms=terms,
                         start_date=start_date,
                         end_date=end_date,
                         start_month=start_month,
                         end_month=end_month,
                         range_label=range_label,
                         current_term=current_term,
                         grouped_projects=grouped_projects,
                         contact=contact,
                         pathways=dropdown_data['pathways'],
                         pathway_mapping=dropdown_data['pathway_mapping'],
                         projects=dropdown_data['projects'],
                         header_title="Programs & Planner")

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
                'icon': r.get('icon'),
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
    plan, updated = planner_service.create_plan(data, current_user.id, club_id)
    if updated:
        return jsonify({'id': plan.id, 'message': 'Plan updated successfully', 'updated': True}), 200
    return jsonify({'id': plan.id, 'message': 'Plan created successfully'}), 201

@planner_bp.route('/api/planner/<int:plan_id>', methods=['PUT'])
@login_required
def update_plan(plan_id):
    data = request.get_json()
    club_id = get_current_club_id()
    planner_service.update_plan(plan_id, data, current_user.id, club_id)
    return jsonify({'message': 'Plan updated successfully'})

@planner_bp.route('/api/planner/<int:plan_id>/cancel', methods=['POST'])
@login_required
def cancel_plan(plan_id):
    club_id = get_current_club_id()
    planner_service.cancel_plan(plan_id, current_user.id, club_id)
    return jsonify({'message': 'Plan cancelled successfully'})

@planner_bp.route('/api/planner/<int:plan_id>', methods=['DELETE'])
@login_required
def delete_plan(plan_id):
    club_id = get_current_club_id()
    planner_service.delete_plan(plan_id, current_user.id, club_id)
    return jsonify({'message': 'Plan deleted successfully'})

@planner_bp.route('/planner/enrollment/<int:enrollment_id>')
@login_required
def enrollment_detail(enrollment_id):
    club_id = get_current_club_id()
    enrollment = ProgramEnrollment.query.filter_by(id=enrollment_id, club_id=club_id).first_or_404()
    
    # Visibility check: mentee, mentor, or admin
    if not (is_authorized(Permissions.PROGRAMS_MANAGE) or 
            enrollment.user_id == current_user.id or 
            enrollment.mentor_user_id == current_user.id):
        abort(403)
        
    if enrollment.status == 'active':
        planner_service.bulk_refresh(enrollment)
    enrollment.progress_stats = planner_service.progress(enrollment)
        
    # Fetch planner tasks
    planner_tasks = Planner.query.filter_by(enrollment_id=enrollment.id)\
        .options(joinedload(Planner.program_task), joinedload(Planner.completed_by))\
        .all()
        
    # Group tasks by phase label
    from collections import defaultdict
    grouped_tasks = defaultdict(list)
    for p in planner_tasks:
        phase = p.program_task.phase_label if (p.program_task and p.program_task.phase_label) else 'Ungrouped'
        grouped_tasks[phase].append(p)
        
    # Sort tasks within each phase by display order / planner id
    for phase in grouped_tasks:
        grouped_tasks[phase].sort(key=lambda p: (p.program_task.display_order if p.program_task else 0, p.id))
        
    # Sort phases
    phases = sorted([p for p in grouped_tasks.keys() if p != 'Ungrouped'])
    if 'Ungrouped' in grouped_tasks:
        phases.append('Ungrouped')
        
    contact = enrollment.mentee.get_contact(club_id)
    
    return render_template('program_enrollment.html',
                           enrollment=enrollment,
                           phases=phases,
                           grouped_tasks=grouped_tasks,
                           contact=contact,
                           header_title=enrollment.program.name)
