from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import current_user
from .auth.utils import login_required, is_authorized
from .auth.permissions import Permissions
from .models import Roster, Meeting, Contact, ContactClub, Pathway, Ticket
from .club_context import get_current_club_id, authorized_club_required
from . import db
from sqlalchemy import distinct
from .utils import get_meetings_by_status
from .services.role_service import RoleService
from .constants import RoleID

from .pathways_routes import get_pathway_library_data

import re
import uuid
import threading

tools_bp = Blueprint('tools_bp', __name__)

# In-memory store for async verification results
# Key: task_id (str), Value: dict with status and result
_verification_tasks = {}
_TASK_TTL_SECONDS = 600  # Auto-cleanup after 10 minutes


def _cleanup_old_tasks():
    """Remove tasks older than TTL."""
    import time
    now = time.time()
    expired = [tid for tid, t in _verification_tasks.items()
               if now - t.get('created_at', 0) > _TASK_TTL_SECONDS]
    for tid in expired:
        _verification_tasks.pop(tid, None)


@tools_bp.route('/', methods=['GET'])
def tools():
    has_lucky_draw_access = is_authorized(Permissions.LUCKY_DRAW_VIEW)
    has_pathways_access = is_authorized(Permissions.PATHWAY_LIB_VIEW)

    if has_pathways_access:
        return redirect(url_for('pathways_bp.pathway_library'))
    elif has_lucky_draw_access:
        return redirect(url_for('lucky_draw_bp.lucky_draw'))
    
    return redirect(url_for('agenda_bp.agenda'))


@tools_bp.route('/level_validator', methods=['GET'])
def level_validator():
    has_lucky_draw_access = is_authorized(Permissions.LUCKY_DRAW_VIEW)
    has_pathways_access = is_authorized(Permissions.PATHWAY_LIB_VIEW)

    pathways = [p.name for p in Pathway.query.filter_by(type='pathway').order_by(Pathway.name).all()]
    programs = [p.name for p in Pathway.query.filter_by(type='program').order_by(Pathway.name).all()]

    return render_template(
        'tools/level_validator.html',
        pathways=pathways,
        programs=programs,
        active_tab='level_validator',
        has_lucky_draw_access=has_lucky_draw_access,
        has_pathways_access=has_pathways_access,
        Permissions=Permissions
    )


@tools_bp.route('/validator', methods=['POST'])
def verify_level():
    """Start an async blockchain verification. Returns a task_id for polling."""
    import time
    _cleanup_old_tasks()

    data = request.get_json()
    if not data:
        return jsonify(success=False, error="Invalid request."), 400

    member_id = (data.get('member_id') or '').strip()
    path_name = (data.get('path_name') or '').strip()
    level = data.get('level')

    # Validate member ID format: PN-xxxxxxxx (PN followed by digits)
    if not member_id or not re.match(r'^PN-\d+$', member_id, re.IGNORECASE):
        return jsonify(success=False, error="Member ID must be in PN-xxxxxxxx format."), 400

    if not path_name:
        return jsonify(success=False, error="Education path is required."), 400

    try:
        level = int(level)
        if level < 1 or level > 5:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify(success=False, error="Level must be between 1 and 5."), 400

    # Create task and start background verification
    task_id = str(uuid.uuid4())
    _verification_tasks[task_id] = {
        'status': 'pending',
        'result': None,
        'created_at': time.time(),
        'params': {'member_id': member_id, 'path_name': path_name, 'level': level}
    }

    def _run_verification(app, tid, mid, pname, lvl):
        with app.app_context():
            from .blockchain import verify_level_on_chain
            result = verify_level_on_chain(mid, pname, lvl)
            if tid in _verification_tasks:
                _verification_tasks[tid]['status'] = 'done'
                _verification_tasks[tid]['result'] = result

    from flask import current_app
    app = current_app._get_current_object()
    thread = threading.Thread(
        target=_run_verification,
        args=(app, task_id, member_id, path_name, level),
        daemon=True
    )
    thread.start()

    return jsonify(success=True, task_id=task_id)


@tools_bp.route('/validator/status/<task_id>', methods=['GET'])
def verify_level_status(task_id):
    """Poll for verification result."""
    task = _verification_tasks.get(task_id)
    if not task:
        return jsonify(success=False, error="Task not found or expired."), 404

    if task['status'] == 'pending':
        return jsonify(success=True, status='pending')

    # Return and keep the result around so user can navigate away and come back
    return jsonify(success=True, status='done', result=task['result'])
