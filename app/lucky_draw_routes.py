from flask import Blueprint, render_template, redirect, url_for
from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
from .club_context import authorized_club_required, filter_by_club
from .models import Roster, Meeting, Contact, Ticket
from .constants import RoleID
from .utils import get_default_meeting_id
from . import db

lucky_draw_bp = Blueprint('lucky_draw_bp', __name__)


@lucky_draw_bp.route('/', methods=['GET'])
@login_required
@authorized_club_required
def lucky_draw():
    if not is_authorized(Permissions.LUCKY_DRAW_VIEW):
        return redirect(url_for('agenda_bp.agenda'))
    
    has_lucky_draw_access = is_authorized(Permissions.LUCKY_DRAW_VIEW)
    has_pathways_access = is_authorized(Permissions.PATHWAY_LIB_VIEW)

    # Get current meeting (using same logic as agenda page)
    selected_meeting_id = get_default_meeting_id()
    current_meeting = None
    if selected_meeting_id:
        current_meeting = db.session.get(Meeting, selected_meeting_id)

    # Get roster entries for this meeting (excluding cancelled entries)
    roster_entries = []
    if current_meeting:
        roster_entries = Roster.query\
            .options(db.joinedload(Roster.roles), db.joinedload(Roster.ticket))\
            .outerjoin(Contact, Roster.contact_id == Contact.id)\
            .filter(Roster.meeting_id == current_meeting.id)\
            .join(Ticket, Roster.ticket_id == Ticket.id)\
            .filter(Ticket.name != 'Cancelled')\
            .order_by(Roster.order_number.asc())\
            .all()

    return render_template(
        'lucky_draw.html',
        current_meeting=current_meeting,
        roster_entries=roster_entries,
        RoleID=RoleID,
        active_tab='luckydraw',
        has_lucky_draw_access=has_lucky_draw_access,
        has_pathways_access=has_pathways_access,
        Permissions=Permissions
    )
