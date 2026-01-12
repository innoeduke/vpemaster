from flask import Blueprint, render_template
from .auth.utils import login_required
from .models import Roster, Meeting, Contact
from . import db

lucky_draw_bp = Blueprint('lucky_draw_bp', __name__)


@lucky_draw_bp.route('/', methods=['GET'])
@login_required
def lucky_draw():
    # Get current meeting (next upcoming or most recent)
    today = db.func.current_date()

    # Find the next upcoming meeting
    current_meeting = Meeting.query\
        .filter(Meeting.Meeting_Date >= today)\
        .order_by(Meeting.Meeting_Date.asc(), Meeting.Meeting_Number.asc())\
        .first()

    # If no upcoming meeting, get the most recent past meeting
    if not current_meeting:
        current_meeting = Meeting.query\
            .filter(Meeting.Meeting_Date < today)\
            .order_by(Meeting.Meeting_Date.desc())\
            .first()

    # Get roster entries for this meeting (excluding cancelled entries)
    roster_entries = []
    table_topic_speakers = []
    if current_meeting:
        roster_entries = Roster.query\
            .outerjoin(Contact, Roster.contact_id == Contact.id)\
            .filter(Roster.meeting_number == current_meeting.Meeting_Number)\
            .filter(Roster.ticket != 'Cancelled')\
            .order_by(Roster.order_number.asc())\
            .all()
        
        # Get table topic speakers (those with Role-taker ticket)
        table_topic_speakers = [
            entry for entry in roster_entries 
            if entry.ticket == 'Role-taker'
        ]

    return render_template(
        'lucky_draw.html',
        current_meeting=current_meeting,
        roster_entries=roster_entries,
        table_topic_speakers=table_topic_speakers
    )
