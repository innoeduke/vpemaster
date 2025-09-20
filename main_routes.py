# vpemaster/main_routes.py

from flask import Blueprint, render_template, request, redirect, url_for, session
from vpemaster.models import User, Contact
from werkzeug.security import check_password_hash
from functools import wraps

main_bp = Blueprint('main_bp', __name__)

# Decorator to check if user is logged in
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('main_bp.login'))
        return f(*args, **kwargs)
    return decorated_function

# Login route
@main_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(Username=username).first()

        if user and check_password_hash(user.Pass_Hash, password):
            session['logged_in'] = True
            session['user_role'] = user.Role
            session['user_id'] = user.id
            session['display_name'] = user.Display_Name # <-- Add this line
            return redirect(url_for('agenda_bp.agenda'))
        else:
            return redirect(url_for('main_bp.login'))
    return render_template('login.html')

# Logout route
@main_bp.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('user_role', None)
    session.pop('user_id', None)
    session.pop('display_name', None) # <-- Add this line
    return redirect(url_for('main_bp.login'))

@main_bp.route('/profile')
@login_required
def profile():
    """
    Displays the logged-in user's profile page.
    """
    user = User.query.get_or_404(session['user_id'])
    contact = None
    if user.Contact_ID:
        contact = Contact.query.get(user.Contact_ID)

    return render_template('profile.html', user=user, contact=contact)

@main_bp.route('/')
@login_required
def index():
    return redirect(url_for('agenda_bp.agenda'))