from flask import Blueprint, render_template, redirect, url_for, request, jsonify, send_from_directory, current_app
from .auth.utils import login_required, current_user
from app.models.meeting import Meeting
from app.club_context import get_current_club_id
from app.utils import get_terms, get_active_term
from sqlalchemy import or_
from sqlalchemy.orm import joinedload
from collections import OrderedDict
from datetime import datetime
import calendar as _cal
import re as _re

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

main_bp = Blueprint('main_bp', __name__)

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('agenda_bp.agenda'))
    return redirect(url_for('clubs_bp.list_clubs'))

@main_bp.route('/calendar')
@login_required
def calendar():
    from app.club_context import is_module_enabled
    from flask import abort
    if not is_module_enabled('Calendar'):
        abort(404)
    club_id = get_current_club_id()
    
    # 1. Fetch all terms for the club
    terms = get_terms()
    
    # 2. Determine date range from query params (accept YYYY-MM-DD or YYYY-MM months)
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

    # 3. Fetch meetings filtered by date range
    date_ranges = []
    if start_date and end_date:
        date_ranges = [(start_date, end_date)]

    query = Meeting.query.options(joinedload(Meeting.sharing_master)).filter_by(club_id=club_id)
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

    # 5. Tally meetings by type for KPI chips (sorted by count desc, first-seen breaks ties)
    raw_counts = OrderedDict()
    for m in meetings:
        type_key = m.type or 'Keynote Speech'
        raw_counts[type_key] = raw_counts.get(type_key, 0) + 1
    meeting_type_counts = OrderedDict(
        sorted(raw_counts.items(), key=lambda kv: (-kv[1], list(raw_counts).index(kv[0])))
    )

    # 6. Map each meeting type to a FontAwesome icon for the KPI tile
    type_icons = {
        'Keynote Speech':     'fa-microphone',
        'Speech Marathon':    'fa-running',
        'Speech Contest':     'fa-trophy',
        'Panel Discussion':   'fa-users',
        'Debate':             'fa-comments',
        'Pecha Kucha':        'fa-stopwatch',
        'Gavel Passing':      'fa-gavel',
        'Club Election':      'fa-vote-yea',
    }

    from app.translations.translations import get_locale as _gl
    _locale = _gl()
    range_label = ''
    if start_date and end_date:
        range_label = f'{_format_month_label(start_date, _locale, compact=True)} — {_format_month_label(end_date, _locale, compact=True)}'

    return render_template('calendar.html',
                         meetings_by_month=meetings_by_month,
                         meeting_type_counts=meeting_type_counts,
                         type_icons=type_icons,
                         total_meetings=len(meetings),
                         start_date=start_date,
                         end_date=end_date,
                         start_month=start_month,
                         end_month=end_month,
                         range_label=range_label,
                         current_term=current_term,
                         header_title="Calendar",
                         today=datetime.now().date(),
                         next_meeting_id=next_meeting_id)

@main_bp.route('/05d9f3b8f0b1f0715520c412e9f8bd74.txt')
def serve_verification_file():
    return send_from_directory(current_app.static_folder, '05d9f3b8f0b1f0715520c412e9f8bd74.txt')


@main_bp.route('/set_language/<language>')
def set_language(language):
    from flask import session, request, redirect, url_for
    if language in ['en', 'zh_CN']:
        session['locale'] = language
    
    referrer = request.referrer
    if referrer and referrer.startswith(request.host_url):
        return redirect(referrer)
    return redirect(url_for('main_bp.index'))