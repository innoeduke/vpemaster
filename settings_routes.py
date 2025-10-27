# vpemaster/settings_routes.py

from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from .main_routes import login_required
from .models import SessionType, User, LevelRole, Presentation
from . import db

settings_bp = Blueprint('settings_bp', __name__)

@settings_bp.route('/settings')
@login_required
def settings():
    """
    Renders the settings page, visible only to administrators.
    """
    if session.get('user_role') != 'Admin':
        return redirect(url_for('agenda_bp.agenda'))

    session_types = SessionType.query.order_by(SessionType.id.asc()).all()
    level_roles = LevelRole.query.order_by(LevelRole.level.asc(), LevelRole.type.desc()).all()
    presentations = Presentation.query.order_by(Presentation.level.asc(), Presentation.code.asc()).all()
    all_users = User.query.order_by(User.Username.asc()).all()
    return render_template('settings.html', session_types=session_types, all_users=all_users, level_roles=level_roles, presentations=presentations)

@settings_bp.route('/settings/sessions/add', methods=['POST'])
@login_required
def add_session_type():
    if session.get('user_role') != 'Admin':
        # This should ideally return a proper error page or flash a message
        return redirect(url_for('agenda_bp.agenda'))

    try:
        new_session = SessionType(
            Title=request.form.get('title'),
            Default_Owner=request.form.get('default_owner') or None,
            Role=request.form.get('role') or None,
            Role_Group=request.form.get('role_group') or None,
            Duration_Min=int(request.form.get('duration_min')) if request.form.get('duration_min') else None,
            Duration_Max=int(request.form.get('duration_max')) if request.form.get('duration_max') else None,
            Is_Section='is_section' in request.form,
            Predefined='predefined' in request.form,
            Valid_for_Project='valid_for_project' in request.form,
            Is_Hidden='is_hidden' in request.form
        )
        db.session.add(new_session)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # In a real app, you'd flash a message: flash(f"Error: {e}", "error")

    return redirect(url_for('settings_bp.settings', default_tab='sessions'))


@settings_bp.route('/settings/sessions/update', methods=['POST'])
@login_required
def update_session_types():
    if session.get('user_role') != 'Admin':
        return jsonify(success=False, message="Permission denied"), 403

    data = request.get_json()
    if not data:
        return jsonify(success=False, message="No data received"), 400

    try:
        for item in data:
            session_type = SessionType.query.get(item['id'])
            if session_type:
                session_type.Title = item.get('Title')
                session_type.Default_Owner = item.get('Default_Owner')
                session_type.Role = item.get('Role')
                session_type.Role_Group = item.get('Role_Group')
                session_type.Is_Section = item.get('Is_Section', False)
                session_type.Predefined= item.get('Predefined', False)
                session_type.Valid_for_Project = item.get('Valid_for_Project', False)
                session_type.Is_Hidden = item.get('Is_Hidden', False)

                duration_min = item.get('Duration_Min')
                session_type.Duration_Min = int(duration_min) if duration_min else None

                duration_max = item.get('Duration_Max')
                session_type.Duration_Max = int(duration_max) if duration_max else None

        db.session.commit()
        return jsonify(success=True, message="Session types updated successfully.")
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500

@settings_bp.route('/settings/level-roles/add', methods=['POST'])
@login_required
def add_level_role():
    if session.get('user_role') != 'Admin':
        return redirect(url_for('agenda_bp.agenda'))

    try:
        new_role = LevelRole(
            level=int(request.form.get('level')),
            role=request.form.get('role'),
            type=request.form.get('type'),
            count_required=int(request.form.get('count_required')) if request.form.get('count_required') else 0
        )
        db.session.add(new_role)
        db.session.commit()
    except Exception as e:
        db.session.rollback()

    return redirect(url_for('settings_bp.settings', default_tab='level-roles'))

@settings_bp.route('/settings/level-roles/update', methods=['POST'])
@login_required
def update_level_roles():
    if session.get('user_role') != 'Admin':
        return jsonify(success=False, message="Permission denied"), 403

    data = request.get_json()
    if not data:
        return jsonify(success=False, message="No data received"), 400

    try:
        for item in data:
            level_role = LevelRole.query.get(item['id'])
            if level_role:
                level_role.level = int(item.get('level')) if item.get('level') else None
                level_role.role = item.get('role')
                level_role.type = item.get('type')
                level_role.count_required = int(item.get('count_required')) if item.get('count_required') else 0

        db.session.commit()
        return jsonify(success=True, message="Level roles updated successfully.")
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500

@settings_bp.route('/settings/presentations/add', methods=['POST'])
@login_required
def add_presentation():
    if session.get('user_role') != 'Admin':
        return redirect(url_for('agenda_bp.agenda'))

    try:
        new_presentation = Presentation(
            level=int(request.form.get('level')),
            code=request.form.get('code'),
            title=request.form.get('title'),
            series=request.form.get('series') or None
        )
        db.session.add(new_presentation)
        db.session.commit()
    except Exception as e:
        db.session.rollback()

    return redirect(url_for('settings_bp.settings', default_tab='presentations'))

@settings_bp.route('/settings/presentations/update', methods=['POST'])
@login_required
def update_presentations():
    if session.get('user_role') != 'Admin':
        return jsonify(success=False, message="Permission denied"), 403

    data = request.get_json()
    if not data:
        return jsonify(success=False, message="No data received"), 400

    try:
        for item in data:
            presentation = Presentation.query.get(item['id'])
            if presentation:
                presentation.level = int(item.get('level')) if item.get('level') else None
                presentation.code = item.get('code')
                presentation.title = item.get('title')
                presentation.series = item.get('series') or None

        db.session.commit()
        return jsonify(success=True, message="Presentations updated successfully.")
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500

