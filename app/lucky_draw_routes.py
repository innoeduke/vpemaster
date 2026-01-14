from flask import Blueprint, render_template
from .auth.utils import login_required
from .models import Roster, Meeting, Contact
from .constants import RoleID
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
    if current_meeting:
        roster_entries = Roster.query\
            .options(db.joinedload(Roster.roles))\
            .outerjoin(Contact, Roster.contact_id == Contact.id)\
            .filter(Roster.meeting_number == current_meeting.Meeting_Number)\
            .filter(Roster.ticket != 'Cancelled')\
            .order_by(Roster.order_number.asc())\
            .all()

    return render_template(
        'lucky_draw.html',
        current_meeting=current_meeting,
        roster_entries=roster_entries,
        RoleID=RoleID
    )
