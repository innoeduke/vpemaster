from flask import Blueprint, render_template, redirect, url_for, request, jsonify, send_from_directory, current_app
from .auth.utils import login_required, current_user
from app.system_messaging import send_system_message
from app.models.user import User
from app.models.meeting import Meeting
from app.club_context import get_current_club_id
from app.utils import get_terms, get_active_term
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
    
    # 1. Fetch all terms for the club
    terms = get_terms()
    
    # 2. Determine date range from query params
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Fallback: if no dates selected, use the active term
    current_term = get_active_term(terms)
    if not start_date and not end_date:
        if current_term:
            start_date = current_term['start']
            end_date = current_term['end']
            
    # 3. Fetch meetings filtered by date range
    date_ranges = []
    if start_date and end_date:
        date_ranges = [(start_date, end_date)]
    
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
        
        from app.translations.translations import get_locale
        if get_locale() == 'zh_CN':
            month_label = m.Meeting_Date.strftime('%Y年%m月')
        else:
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
                         start_date=start_date,
                         end_date=end_date,
                         current_term=current_term,
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


@main_bp.route('/set_language/<language>')
def set_language(language):
    from flask import session, request, redirect, url_for
    if language in ['en', 'zh_CN']:
        session['locale'] = language
    
    referrer = request.referrer
    if referrer and referrer.startswith(request.host_url):
        return redirect(referrer)
    return redirect(url_for('main_bp.index'))