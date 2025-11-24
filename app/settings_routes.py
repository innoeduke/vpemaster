# vpemaster/settings_routes.py

from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, current_app, flash
from .auth.utils import login_required, is_authorized
from .models import SessionType, User, LevelRole, Presentation, Role
from . import db
from .utils import load_all_settings
import csv
import os

settings_bp = Blueprint('settings_bp', __name__)


@settings_bp.route('/settings')
@login_required
def settings():
    """
    Renders the settings page, visible only to administrators.
    """
    if not is_authorized(session.get('user_role'), 'SETTINGS_VIEW_ALL'):
        return redirect(url_for('agenda_bp.agenda'))

    all_settings = load_all_settings()
    
    club_settings_raw = all_settings.get('ClubSettings', {})

    # Transform keys from .ini file (e.g., 'club name') 
    # to what the template expects (e.g., 'club_name')
    general_settings = {
        key.replace(' ', '_'): value 
        for key, value in club_settings_raw.items()
    }

    session_types = SessionType.query.order_by(SessionType.id.asc()).all()
    level_roles = LevelRole.query.order_by(
        LevelRole.level.asc(), LevelRole.type.desc()).all()
    presentations = Presentation.query.order_by(
        Presentation.level.asc(), Presentation.code.asc()).all()
    all_users = User.query.order_by(User.Username.asc()).all()
    roles_query = Role.query.order_by(Role.name.asc()).all()
    roles = [{'id': role.id, 'name': role.name} for role in roles_query]
    print(roles)
    return render_template('settings.html', session_types=session_types, all_users=all_users, level_roles=level_roles, presentations=presentations, general_settings=general_settings, roles=roles)


@settings_bp.route('/settings/sessions/add', methods=['POST'])
@login_required
def add_session_type():
    if not is_authorized(session.get('user_role'), 'SETTINGS_VIEW_ALL'):
        return jsonify(success=False, message="Permission denied"), 403

    try:
        # 输入验证和清理
        title = request.form.get('title', '').strip()
        if not title:
            return jsonify(success=False, message="Title is required"), 400
        
        # 检查标题是否已存在
        existing_session = SessionType.query.filter_by(Title=title).first()
        if existing_session:
            return jsonify(success=False, message="Session type with this title already exists"), 400
        
        # 验证数值输入
        duration_min_str = request.form.get('duration_min', '').strip()
        duration_max_str = request.form.get('duration_max', '').strip()
        
        duration_min = None
        duration_max = None
        
        if duration_min_str:
            if not duration_min_str.isdigit():
                return jsonify(success=False, message="Duration min must be a positive integer"), 400
            duration_min = int(duration_min_str)
            if duration_min < 1 or duration_min > 480:  # 8小时限制
                return jsonify(success=False, message="Duration min must be between 1 and 480 minutes"), 400
        
        if duration_max_str:
            if not duration_max_str.isdigit():
                return jsonify(success=False, message="Duration max must be a positive integer"), 400
            duration_max = int(duration_max_str)
            if duration_max < 1 or duration_max > 480:
                return jsonify(success=False, message="Duration max must be between 1 and 480 minutes"), 400
        
        # 验证时长逻辑
        if duration_min and duration_max and duration_min > duration_max:
            return jsonify(success=False, message="Duration min cannot be greater than duration max"), 400

        role_id_str = request.form.get('role_id', '').strip()
        role_id = int(role_id_str) if role_id_str else None

        new_session = SessionType(
            Title=title,
            Default_Owner=request.form.get('default_owner', '').strip() or None,
            role_id=role_id,
            Duration_Min=duration_min,
            Duration_Max=duration_max,
            Is_Section='is_section' in request.form,
            Predefined='predefined' in request.form,
            Valid_for_Project='valid_for_project' in request.form,
            Is_Hidden='is_hidden' in request.form
        )
        db.session.add(new_session)
        db.session.commit()
        
        return jsonify(success=True, message="Session type added successfully", id=new_session.id)
        
    except ValueError as e:
        db.session.rollback()
        current_app.logger.error(f"Value error adding session type: {str(e)}")
        return jsonify(success=False, message="Invalid input data"), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error adding session type: {str(e)}")
        return jsonify(success=False, message="Internal server error"), 500


@settings_bp.route('/settings/sessions/update', methods=['POST'])
@login_required
def update_session_types():
    if not is_authorized(session.get('user_role'), 'SETTINGS_VIEW_ALL'):
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
                role_id_str = item.get('role_id')
                session_type.role_id = int(role_id_str) if role_id_str else None
                session_type.Is_Section = item.get('Is_Section', False)
                session_type.Predefined = item.get('Predefined', False)
                session_type.Valid_for_Project = item.get(
                    'Valid_for_Project', False)
                session_type.Is_Hidden = item.get('Is_Hidden', False)

                duration_min = item.get('Duration_Min')
                session_type.Duration_Min = int(
                    duration_min) if duration_min else None

                duration_max = item.get('Duration_Max')
                session_type.Duration_Max = int(
                    duration_max) if duration_max else None

        db.session.commit()
        return jsonify(success=True, message="Session types updated successfully.")
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@settings_bp.route('/settings/level-roles/add', methods=['POST'])
@login_required
def add_level_role():
    if not is_authorized(session.get('user_role'), 'SETTINGS_VIEW_ALL'):
        return redirect(url_for('agenda_bp.agenda'))

    try:
        new_role = LevelRole(
            level=int(request.form.get('level')),
            role=request.form.get('role'),
            type=request.form.get('type'),
            count_required=int(request.form.get('count_required')) if request.form.get(
                'count_required') else 0
        )
        db.session.add(new_role)
        db.session.commit()
    except Exception as e:
        db.session.rollback()

    return redirect(url_for('settings_bp.settings', default_tab='level-roles'))


@settings_bp.route('/settings/level-roles/update', methods=['POST'])
@login_required
def update_level_roles():
    if not is_authorized(session.get('user_role'), 'SETTINGS_VIEW_ALL'):
        return jsonify(success=False, message="Permission denied"), 403

    data = request.get_json()
    if not data:
        return jsonify(success=False, message="No data received"), 400

    try:
        for item in data:
            level_role = LevelRole.query.get(item['id'])
            if level_role:
                level_role.level = int(
                    item.get('level')) if item.get('level') else None
                level_role.role = item.get('role')
                level_role.type = item.get('type')
                level_role.count_required = int(
                    item.get('count_required')) if item.get('count_required') else 0

        db.session.commit()
        return jsonify(success=True, message="Level roles updated successfully.")
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


@settings_bp.route('/settings/presentations/add', methods=['POST'])
@login_required
def add_presentation():
    if not is_authorized(session.get('user_role'), 'SETTINGS_VIEW_ALL'):
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
    if not is_authorized(session.get('user_role'), 'SETTINGS_VIEW_ALL'):
        return jsonify(success=False, message="Permission denied"), 403

    data = request.get_json()
    if not data:
        return jsonify(success=False, message="No data received"), 400

    try:
        for item in data:
            presentation = Presentation.query.get(item['id'])
            if presentation:
                presentation.level = int(
                    item.get('level')) if item.get('level') else None
                presentation.code = item.get('code')
                presentation.title = item.get('title')
                presentation.series = item.get('series') or None

        db.session.commit()
        return jsonify(success=True, message="Presentations updated successfully.")
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500


import io

@settings_bp.route('/settings/roles/import', methods=['POST'])
@login_required
def import_roles():
    if not is_authorized(session.get('user_role'), 'SETTINGS_VIEW_ALL'):
        return redirect(url_for('agenda_bp.agenda'))

    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('settings_bp.settings', _anchor='agenda-settings'))

    file = request.files['file']

    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('settings_bp.settings', _anchor='agenda-settings'))

    if file and file.filename.endswith('.csv'):
        try:
            # Read the file in-memory
            stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
            reader = csv.DictReader(stream)
            
            for row in reader:
                role_name = row.get('name')
                if role_name and not Role.query.filter_by(name=role_name).first():
                    new_role = Role(
                        name=role_name,
                        icon=row.get('icon'),
                        type=row.get('type'),
                        award_category=row.get('award_category'),
                        needs_approval=row.get('needs_approval', '0').strip() == '1',
                        is_distinct=row.get('is_distinct', '0').strip() == '1'
                    )
                    db.session.add(new_role)
            
            db.session.commit()
            flash('Roles have been successfully imported.', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'An error occurred: {e}', 'danger')
    else:
        flash('Invalid file format. Please upload a .csv file.', 'danger')

    return redirect(url_for('settings_bp.settings', _anchor='agenda-settings'))
