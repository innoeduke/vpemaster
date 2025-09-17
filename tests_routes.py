# vpemaster/tests_routes.py

from flask import Blueprint, render_template, session, redirect, url_for
from .main_routes import login_required

tests_bp = Blueprint('tests_bp', __name__)

@tests_bp.route('/test')
@login_required
def test_page():
    """
    Renders the test page, visible only to administrators.
    """
    if session.get('user_role') != 'Admin':
        return redirect(url_for('agenda_bp.agenda'))

    return render_template('tests.html')