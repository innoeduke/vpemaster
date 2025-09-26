# vpemaster/settings_routes.py

from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from .main_routes import login_required
from .models import SessionType, User
from vpemaster import db

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

    all_users = User.query.order_by(User.Username.asc()).all()
    return render_template('settings.html', session_types=session_types, all_users=all_users)

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
                session_type.Is_Titleless = item.get('Is_Titleless', False)
                session_type.Valid_for_Project = item.get('Valid_for_Project', False)

                duration_min = item.get('Duration_Min')
                session_type.Duration_Min = int(duration_min) if duration_min else None

                duration_max = item.get('Duration_Max')
                session_type.Duration_Max = int(duration_max) if duration_max else None

        db.session.commit()
        return jsonify(success=True, message="Session types updated successfully.")
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, message=str(e)), 500

