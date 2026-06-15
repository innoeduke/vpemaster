"""Template Manager blueprint.

Gated routes for club users with ``MEETING_MANAGE`` permission to list, open,
edit, delete, copy-from-seed, and export-from-meeting for the current club's
meeting templates. All operations are scoped to ``session['current_club_id']``.
"""
from flask import (
    Blueprint, abort, jsonify, make_response, redirect, render_template,
    request, url_for,
)

from . import db
from .auth.utils import club_permission_required
from .auth.permissions import Permissions
from .club_context import authorized_club_required, get_current_club_id
from .models import Meeting, MeetingRole, SessionLog, SessionType
from .services import meeting_template_service as tpl_service
from .services.meeting_template_service import (
    TemplateNameInvalid, TemplateNotFound, TemplatePathEscape,
    TemplateError,
)


template_bp = Blueprint('template_manager_bp', __name__)


def _no_cache(response):
    """Disable browser and bfcache so the editor always shows fresh server state."""
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


def _redirect_with_notice(notice=None, error=None, **extra):
    """Redirect to the list view, optionally carrying a notice/error message."""
    params = dict(extra)
    if notice:
        params['notice'] = notice
    if error:
        params['error'] = error
    return redirect(url_for('template_manager_bp.list_templates', **params))


@template_bp.route('/meetings/templates', methods=['GET'])
@authorized_club_required
@club_permission_required(Permissions.MEETING_MANAGE)
def list_templates():
    """List the current club's templates with create actions."""
    club_id = get_current_club_id()
    templates = tpl_service.list_templates(club_id)

    meetings = []
    if request.args.get('show_export'):
        meetings = (
            db.session.query(Meeting)
            .filter(Meeting.club_id == club_id)
            .order_by(Meeting.Meeting_Date.desc())
            .limit(50)
            .all()
        )

    return _no_cache(make_response(render_template(
        'template_manager/list.html',
        templates=templates,
        meetings=meetings,
        show_export_form=bool(request.args.get('show_export')),
        notice=request.args.get('notice'),
        error=request.args.get('error'),
    )))


@template_bp.route('/meetings/templates/new', methods=['POST'])
@authorized_club_required
@club_permission_required(Permissions.MEETING_MANAGE)
def create_blank():
    """Create a blank template (header row only) and redirect to the editor."""
    club_id = get_current_club_id()
    name = (request.form.get('name') or '').strip()
    if not name:
        return _redirect_with_notice(error='Template name is required.')

    try:
        filename = tpl_service.create_blank(club_id, name)
    except TemplateNameInvalid as exc:
        return _redirect_with_notice(error=str(exc))
    except TemplateError as exc:
        return _redirect_with_notice(error=str(exc))

    return redirect(url_for('template_manager_bp.edit_template', name=filename, notice='Template created. Add sessions in the editor.'))


@template_bp.route('/meetings/templates/export', methods=['POST'])
@authorized_club_required
@club_permission_required(Permissions.MEETING_MANAGE)
def export_from_meeting():
    """Persist a meeting's SessionLog rows as a new club template."""
    club_id = get_current_club_id()
    meeting_id = request.form.get('meeting_id', type=int)
    template_name = request.form.get('template_name', '').strip()

    if not meeting_id or not template_name:
        return _redirect_with_notice(error='Meeting and template name are required.', show_export=1)

    meeting = db.session.get(Meeting, meeting_id)
    if not meeting or meeting.club_id != club_id:
        return _redirect_with_notice(error='Meeting not found in this club.', show_export=1)

    logs = (
        SessionLog.query
        .filter_by(meeting_id=meeting_id)
        .order_by(SessionLog.Meeting_Seq.asc())
        .all()
    )
    try:
        filename = tpl_service.export_meeting_logs(club_id, logs, template_name)
    except TemplateNameInvalid as exc:
        return _redirect_with_notice(error=str(exc), show_export=1)
    except TemplateError as exc:
        return _redirect_with_notice(error=str(exc), show_export=1)

    return redirect(url_for('template_manager_bp.edit_template', name=filename, notice='Template exported from meeting.'))


@template_bp.route('/meetings/templates/edit/<path:name>', methods=['GET'])
@authorized_club_required
@club_permission_required(Permissions.MEETING_MANAGE)
def edit_template(name):
    """Render the editor for a single template."""
    club_id = get_current_club_id()
    try:
        payload = tpl_service.get_template(club_id, name)
    except (TemplateNotFound, TemplateNameInvalid, TemplatePathEscape):
        abort(404)

    session_types = SessionType.get_all_for_club(club_id)
    type_choices = sorted({st.Title for st in session_types} | {'Section', 'Generic'})

    roles = [r.name for r in MeetingRole.get_all_for_club(club_id)]

    return _no_cache(make_response(render_template(
        'template_manager/editor.html',
        template_name=name,
        rows=payload['rows'],
        type_choices=type_choices,
        roles=roles,
        notice=request.args.get('notice'),
    )))


@template_bp.route('/meetings/templates/edit/<path:name>', methods=['POST'])
@authorized_club_required
@club_permission_required(Permissions.MEETING_MANAGE)
def save_template(name):
    """Persist the editor's row list back to the template CSV."""
    club_id = get_current_club_id()
    payload = request.get_json(silent=True) or {}
    rows = payload.get('rows')
    if not isinstance(rows, list):
        return jsonify(success=False, message='Invalid payload'), 400

    try:
        tpl_service.save_template(club_id, name, rows)
    except (TemplateNameInvalid, TemplatePathEscape) as exc:
        return jsonify(success=False, message=str(exc)), 400
    except TemplateNotFound:
        return jsonify(success=False, message='Template not found'), 404
    except TemplateError as exc:
        return jsonify(success=False, message=str(exc)), 500

    return jsonify(success=True, redirect=url_for('template_manager_bp.list_templates'))


@template_bp.route('/meetings/templates/delete', methods=['POST'])
@authorized_club_required
@club_permission_required(Permissions.MEETING_MANAGE)
def delete_template():
    """Delete a template (current club only)."""
    club_id = get_current_club_id()
    name = (request.form.get('name') or '').strip()
    if not name:
        json_body = request.get_json(silent=True) or {}
        if isinstance(json_body, dict):
            name = (json_body.get('name') or '').strip()
    if not name:
        return jsonify(success=False, message='Template name is required'), 400

    try:
        tpl_service.delete_template(club_id, name)
    except TemplateNotFound:
        return jsonify(success=False, message='Template not found'), 404
    except (TemplateNameInvalid, TemplatePathEscape) as exc:
        return jsonify(success=False, message=str(exc)), 400

    return jsonify(success=True)
