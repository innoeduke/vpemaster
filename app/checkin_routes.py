"""Public Self Check-In endpoints.

Reachable without authentication via a signed token printed/projected as a QR
code. Officer-side QR/toggle endpoints live in roster_routes.py (they require
ROSTER_EDIT permission).

Routes:
    GET  /checkin/<token>                 — public list of roster entries.
    POST /checkin/<token>/mark/<int:id>   — public self check-in (idempotent).
"""
from datetime import datetime

from flask import Blueprint, abort, jsonify, render_template, request

from . import db
from .club_context import is_module_enabled, set_current_club_id
from .models import Meeting, Roster
from .services.checkin_service import verify_checkin_token


checkin_bp = Blueprint('checkin_bp', __name__)


_ACTIVE_STATUSES = ('not started', 'running')


def _resolve_meeting(token):
    """Decode token -> Meeting, enforcing module flag and active status. Returns
    Meeting on success; raises 404 otherwise. Also sets the current club context
    so other downstream helpers (e.g. context processors) work correctly for the
    anonymous request.
    """
    meeting_id = verify_checkin_token(token)
    if not meeting_id:
        abort(404)

    meeting = db.session.get(Meeting, meeting_id)
    if not meeting:
        abort(404)

    if not is_module_enabled('Self Check-In', meeting.club_id):
        abort(404)

    if meeting.status not in _ACTIVE_STATUSES:
        abort(404)

    set_current_club_id(meeting.club_id)
    return meeting


@checkin_bp.route('/<token>', methods=['GET'])
def checkin_page(token):
    """Mobile-friendly page listing the meeting's roster so a guest can find
    their own entry and tap to check in."""
    meeting = _resolve_meeting(token)

    entries = (
        Roster.query
        .options(
            db.joinedload(Roster.contact),
            db.joinedload(Roster.roles),
            db.joinedload(Roster.ticket),
        )
        .filter(Roster.meeting_id == meeting.id)
        .all()
    )

    # Hide cancelled rows and rows without a contact (placeholder/unallocated).
    visible = []
    for e in entries:
        if not e.contact:
            continue
        if e.ticket and e.ticket.name == 'Cancelled':
            continue
        visible.append({
            'id': e.id,
            'name': e.contact.Name,
            'contact_type': e.contact_type or (e.contact.Type if e.contact else None),
            'roles': [r.name for r in e.roles] if e.roles else [],
            'checked_in_at': e.checked_in_at.isoformat() if e.checked_in_at else None,
        })

    # Sort alphabetically — guests scan visually for their own name.
    visible.sort(key=lambda x: (x['name'] or '').lower())

    club_name = meeting.club.club_name if meeting.club else ''

    return render_template(
        'checkin.html',
        token=token,
        meeting=meeting,
        club_name=club_name,
        entries=visible,
    )


@checkin_bp.route('/<token>/mark/<int:roster_id>', methods=['POST'])
def mark_checkin(token, roster_id):
    """Set checked_in_at on the roster row. Idempotent — re-tap returns the
    existing timestamp with already=True so the UI can stay calm."""
    meeting = _resolve_meeting(token)

    entry = db.session.get(Roster, roster_id)
    if not entry or entry.meeting_id != meeting.id:
        abort(404)

    if entry.checked_in_at:
        return jsonify({
            'success': True,
            'already': True,
            'checked_in_at': entry.checked_in_at.isoformat(),
            'checked_in_via': entry.checked_in_via,
        })

    entry.checked_in_at = datetime.utcnow()
    entry.checked_in_via = 'self'
    entry.checked_in_by_user_id = None
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

    return jsonify({
        'success': True,
        'already': False,
        'checked_in_at': entry.checked_in_at.isoformat(),
        'checked_in_via': entry.checked_in_via,
    })
