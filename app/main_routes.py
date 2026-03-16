from flask import Blueprint, render_template, redirect, url_for, request, jsonify, send_from_directory, current_app
from .auth.utils import login_required, current_user
from app.system_messaging import send_system_message
from app.models.user import User
from app.models.meeting import Meeting
from app.club_context import get_current_club_id
from app.utils import get_terms, get_active_term, get_date_ranges_for_terms
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from collections import OrderedDict
from datetime import datetime

main_bp = Blueprint('main_bp', __name__)

@main_bp.route('/')
@login_required
def index():
    return redirect(url_for('agenda_bp.agenda'))

@main_bp.route('/calendar')
@login_required
def calendar():
    club_id = get_current_club_id()
    
    # 1. Fetch all terms for the club to show in the filter
    terms = get_terms()
    
    # 2. Determine selected terms
    selected_term_ids = request.args.getlist('term')
    
    # Fallback: if no term selected, use the active term
    current_term = get_active_term(terms)
    if not selected_term_ids:
        if current_term:
            selected_term_ids = [current_term['id']]
        elif terms:
            selected_term_ids = [terms[0]['id']]
            
    # 3. Fetch meetings filtered by term date ranges
    date_ranges = get_date_ranges_for_terms(selected_term_ids, terms)
    
    query = Meeting.query.options(joinedload(Meeting.manager)).filter_by(club_id=club_id)
    if date_ranges:
        conditions = [Meeting.Meeting_Date.between(start, end) for start, end in date_ranges]
        query = query.filter(or_(*conditions))
    
    meetings = query.order_by(Meeting.Meeting_Date.asc()).all()
    
    # 4. Group meetings by month and week
    meetings_by_month = OrderedDict()
    for m in meetings:
        if not m.Meeting_Date:
            continue
            
        month_key = m.Meeting_Date.strftime('%Y-%m')
        month_label = m.Meeting_Date.strftime('%B %Y')
        
        if month_key not in meetings_by_month:
            meetings_by_month[month_key] = {
                'label': month_label,
                'weeks': {i: [] for i in range(1, 5)}
            }
        
        week_num = (m.Meeting_Date.day - 1) // 7 + 1
        if week_num > 4:
            week_num = 4
            
        meetings_by_month[month_key]['weeks'][week_num].append(m)
        
    next_meeting = Meeting.query.filter(
        Meeting.club_id == club_id,
        Meeting.Meeting_Date >= datetime.now().date(),
        Meeting.status != 'cancelled'
    ).order_by(Meeting.Meeting_Date.asc()).first()
    next_meeting_id = next_meeting.id if next_meeting else None

    return render_template('calendar.html',
                         meetings_by_month=meetings_by_month,
                         terms=terms,
                         selected_term_ids=selected_term_ids,
                         header_title="Calendar",
                         today=datetime.now().date(),
                         next_meeting_id=next_meeting_id)

@main_bp.route('/05d9f3b8f0b1f0715520c412e9f8bd74.txt')
def serve_verification_file():
    return send_from_directory(current_app.static_folder, '05d9f3b8f0b1f0715520c412e9f8bd74.txt')

@main_bp.route('/api/report-bug', methods=['POST'])
@login_required
def report_bug():
    try:
        data = request.get_json()
        subject = data.get('subject')
        description = data.get('description')
        
        if not description:
            return jsonify({'success': False, 'error': 'Description is required'}), 400
            
        # Find SysAdmin user
        sysadmin = User.query.filter_by(username='sysadmin').first()
        
        if not sysadmin:
            return jsonify({'success': False, 'error': 'System administrator not found'}), 404
            
        full_subject = f"Bug Report: {subject}"
        body = f"User: {current_user.username} ({current_user.display_name})\n\n{description}"
        
        success, message = send_system_message(sysadmin.id, full_subject, body)
        
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': message}), 500
            
    except Exception as e:
        print(f"Error reporting bug: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500