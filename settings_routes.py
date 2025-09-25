# vpemaster/settings_routes.py

from flask import Blueprint, render_template, session, redirect, url_for
from .main_routes import login_required

settings_bp = Blueprint('settings_bp', __name__)

@settings_bp.route('/settings')
@login_required
def settings():
    """
    Renders the settings page, which is accessible only by administrators.
    This page will feature a tabbed interface for various system settings.
    """
    if session.get('user_role') != 'Admin':
        return redirect(url_for('agenda_bp.agenda'))

    return render_template('settings.html')
